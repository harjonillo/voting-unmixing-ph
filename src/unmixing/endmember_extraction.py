import numpy as np
from scipy.linalg import det, svd, pinv  # svd for full SVD, pinv for pseudo-inverse
from scipy.sparse.linalg import (
    svds as sparse_svds,
)  # For partial SVD (like MATLAB's svds)
from scipy.spatial import ConvexHull  # For convhulln equivalent
import warnings
from tqdm import tqdm  # For progress bar
from scipy.optimize import nnls


def nfindr(y_proj):
    """
    N-FINDR endmember extraction algorithm.

    Finds the simplex of maximum volume whose vertices lie within the data
    cloud, under the assumption that the endmembers correspond to the
    purest (most extreme) pixels.  The number of endmembers extracted is
    fixed by the dimensionality of the input: p = Nb_bandes + 1.

    The search is restricted to the convex-hull envelope when p < 7
    (using ``scipy.spatial.ConvexHull``), falling back to all pixels
    otherwise.  Progress is displayed via a tqdm bar.

    Parameters
    ----------
    y_proj : ndarray, shape (Nb_pix, Nb_bandes)
        Dimensionality-reduced hyperspectral data, typically the output of
        PCA with Nb_bandes = p - 1 retained components.

    Returns
    -------
    endm : ndarray, shape (Nb_bandes, Nb_endm)
        Extracted endmember signatures, one per column.
    critere_opt : float
        Negative absolute determinant of the optimal simplex matrix
        (the volume criterion being maximised; more negative = larger volume).
    """
    Nb_pix, Nb_bandes = y_proj.shape
    Nb_endm = Nb_bandes + 1  # Number of endmembers is determined by the dimensionality

    # Quick hull if size allows it (equivalent to MATLAB's convhulln)
    if Nb_endm < 7 and Nb_pix >= Nb_endm:  # Ensure enough points for hull
        try:
            # ConvexHull expects (N_points, N_dimensions)
            hull = ConvexHull(y_proj)
            ind_envlp = np.unique(hull.vertices)  # Vertices are indices
        except Exception as e:
            warnings.warn(
                f"ConvexHull failed ({e}), falling back to all pixels for envelope."
            )
            ind_envlp = np.arange(Nb_pix)
    else:
        ind_envlp = np.arange(Nb_pix)  # All pixels considered if not using quick hull

    envlp = y_proj[ind_envlp, :]
    Nb_pix_envlp = len(ind_envlp)

    # INITIALIZATION
    # Choice of Nb_endm pixels
    if Nb_pix_envlp < Nb_endm:
        raise ValueError(
            f"Not enough unique pixels ({Nb_pix_envlp}) in the envelope to select {Nb_endm} endmembers."
        )

    ind_perm = np.random.permutation(Nb_pix_envlp)
    combi = np.sort(ind_perm[:Nb_endm])  # Indices within envlp

    # Calculate criterion (volume)
    candidat_opt = envlp[combi, :].T  # (Nb_bandes x Nb_endm)

    # Check if the matrix for determinant is square and invertible
    matrix_for_det = np.vstack([candidat_opt, np.ones((1, Nb_endm))])
    if matrix_for_det.shape[0] != matrix_for_det.shape[1]:
        # This should ideally not happen if Nb_endm = Nb_bandes + 1
        raise ValueError(
            f"Matrix for determinant is not square: {matrix_for_det.shape}. "
            f"Expected ({Nb_bandes}+1)x{Nb_endm} = {Nb_endm}x{Nb_endm}."
        )

    critere_opt = -np.abs(det(matrix_for_det))

    # Algorithm
    # Replacing MATLAB's waitbar with tqdm for console progress
    print(f"N-FINDR: Searching for {Nb_endm} endmembers...")

    # Store the best combination of indices from `envlp`
    best_combi_indices_in_envlp = combi.copy()

    # Total iterations for progress bar
    total_iterations = Nb_endm * Nb_pix_envlp

    with tqdm(total=total_iterations, desc="N-FINDR Progress", unit="iter") as pbar:
        for ind_endm_idx in range(
            Nb_endm
        ):  # Loop through each position in the combination
            for ind_pix_idx in range(
                Nb_pix_envlp
            ):  # Loop through each pixel in the envelope
                pbar.update(1)  # Update progress bar

                combi_cand = (
                    best_combi_indices_in_envlp.copy()
                )  # Start with current best combination
                combi_cand[ind_endm_idx] = (
                    ind_pix_idx  # Replace one element with a candidate pixel index from envlp
                )

                # Check if the candidate combination has unique indices
                if len(np.unique(combi_cand)) == Nb_endm:
                    candidat_cand = envlp[combi_cand, :].T  # (Nb_bandes x Nb_endm)

                    # Calculate criterion for candidate combination
                    matrix_for_det_cand = np.vstack(
                        [candidat_cand, np.ones((1, Nb_endm))]
                    )
                    critere_cand = -np.abs(det(matrix_for_det_cand))

                    # Test: if new criterion is better (smaller negative value means larger volume)
                    if critere_cand < critere_opt:
                        critere_opt = critere_cand
                        candidat_opt = candidat_cand
                        best_combi_indices_in_envlp = (
                            combi_cand.copy()
                        )  # Update the best combination

    endm = candidat_opt  # The optimal endmembers (Nb_bandes x Nb_endm)
    return endm, critere_opt


def _estimate_snr(R_data, r_m, x):
    """
    Internal helper function to estimate Signal-to-Noise Ratio (SNR).
    Translated from MATLAB's estimate_snr.

    Args:
        R_data (np.ndarray): Hyperspectral data matrix (L channels x N pixels).
        r_m (np.ndarray): Mean of each band (L x 1).
        x (np.ndarray): Data projected onto p-subspace (p x N).

    Returns:
        float: Estimated SNR in dB.
    """
    L, N = R_data.shape
    p, _ = x.shape

    P_y = np.sum(R_data**2) / N
    P_x = (
        np.sum(x**2) / N + (r_m.T @ r_m).item()
    )  # .item() to get scalar from 1x1 array

    # Handle potential division by zero or negative values in log argument
    numerator = P_x - (p / L) * P_y
    denominator = P_y - P_x

    if denominator <= 0 or numerator <= 0:
        warnings.warn(
            "SNR estimation: Denominator or numerator for log10 is non-positive. Returning -inf."
        )
        return -np.inf  # Or handle as an error if appropriate

    snr_est = 10 * np.log10(numerator / denominator)
    return snr_est


def vca(R, **kwargs):
    """
    Vertex Component Analysis (VCA) endmember extraction algorithm.

    Identifies the p purest pixels in the data by sequentially finding
    vectors maximally orthogonal to the subspace already spanned by the
    selected endmembers.  The projection used (projective vs. subspace)
    is chosen automatically based on the estimated or user-supplied SNR
    relative to the threshold  SNR_th = 15 + 10 log10(p)  dB.

    Parameters
    ----------
    R : ndarray, shape (L, N)
        Hyperspectral data matrix: L spectral channels, N pixels.
    **kwargs
        Endmembers : int
            Number of endmembers p to extract.  Required.
        SNR : float, optional
            Signal-to-noise ratio in dB.  If omitted, SNR is estimated
            from the data using the method in [1].
        verbose : str, optional
            'on' (default) prints SNR and projection-type messages;
            'off' suppresses all output.

    Returns
    -------
    Ae : ndarray, shape (L, p)
        Estimated endmember (mixing) matrix, one signature per column.
    indice : ndarray, shape (p,)
        0-based pixel indices of the selected pure pixels.
    Rp : ndarray, shape (L, N)
        Data projected onto the identified p-dimensional subspace.
    SNR : float
        SNR value used (estimated or user-supplied), in dB.
    Ud : ndarray, shape (L, d)
        Isometric matrix of the subspace used for projection.
    x : ndarray, shape (d, N)
        Data coordinates in the projected subspace.

    Notes
    -----
    TODO: normalise endmembers in Ae to unit norm.

    References
    ----------
    [1] J. M. P. Nascimento and J. M. Bioucas-Dias, "Vertex component
        analysis: A fast algorithm to unmix hyperspectral data,"
        IEEE TGRS, vol. 43, no. 4, pp. 898–910, 2005.
    """
    # Default parameters
    verbose = "on"
    snr_input = 0  # Flag: 0 means estimate SNR, 1 means user provided SNR
    p = None  # Number of endmembers (required input)
    SNR = None  # SNR value

    # Parse keyword arguments
    for key, value in kwargs.items():
        key_lower = key.lower()
        if key_lower == "verbose":
            verbose = value
        elif key_lower == "endmembers":
            p = value
        elif key_lower == "snr":
            SNR = value
            snr_input = 1
        else:
            warnings.warn(f"Unrecognized parameter: {key}")

    # Input validation
    if R is None or R.size == 0:
        raise ValueError("There is no data (R is empty).")

    L, N = R.shape  # L: number of channels, N: number of pixels

    if p is None:
        raise ValueError("'Endmembers' parameter (p) is required.")
    if not (isinstance(p, int) and 1 <= p <= L):
        raise ValueError(
            f"ENDMEMBER parameter (p) must be an integer between 1 and L ({L}). Got {p}."
        )

    # SNR Estimates
    if snr_input == 0:
        r_m = np.mean(R, axis=1, keepdims=True)  # Mean of each band (L x 1)
        R_o = R - r_m  # Data with zero-mean (L x N)

        try:
            Ud, Sd, Vd = sparse_svds(R_o @ R_o.T / N, k=p)
            idx_sorted = np.argsort(Sd)[::-1]
            Ud = Ud[:, idx_sorted]
            Sd = Sd[idx_sorted]
            Vd = Vd[idx_sorted, :]
        except Exception as e:
            warnings.warn(f"sparse_svds failed, falling back to full SVD: {e}")
            u_full, s_full, vh_full = np.linalg.svd(R_o @ R_o.T / N)
            Ud = u_full[:, :p]
            Sd = s_full[:p]
            Vd = vh_full[:p, :]

        x_p = Ud.T @ R_o  # Project the zero-mean data onto p-subspace (p x N)

        SNR = _estimate_snr(R, r_m, x_p)

        if verbose == "on":
            print(f"SNR estimated = {SNR:.4f}[dB]")
    else:
        if verbose == "on":
            print(f"input    SNR = {SNR:.4f}[dB]\t")

    SNR_th = 15 + 10 * np.log10(p)

    # Choosing Projective Projection or projection to p-1 subspace
    if SNR < SNR_th:
        if verbose == "on":
            print("... Select the projective proj.")

        d = p - 1

        # Corrected: x must be sliced from x_p to d rows
        x = x_p[:d, :]  # This corresponds to MATLAB's x = x_p(1:d,:);

        if snr_input == 0:
            # Ud already has top p components from previous step.
            # We need to take top d components from Ud.
            Ud = Ud[:, :d]
        else:
            r_m = np.mean(R, axis=1, keepdims=True)
            R_o = R - r_m

            try:
                Ud, Sd, Vd = sparse_svds(R_o @ R_o.T / N, k=d)
                idx_sorted = np.argsort(Sd)[::-1]
                Ud = Ud[:, idx_sorted]
            except Exception as e:
                warnings.warn(f"sparse_svds failed, falling back to full SVD: {e}")
                u_full, s_full, vh_full = np.linalg.svd(R_o @ R_o.T / N)
                Ud = u_full[:, :d]

            x = Ud.T @ R_o  # This x is already (d x N), so no further slicing needed.
            # SNR = _estimate_snr(R, r_m, x_p)  # recalculate SNR on the p-1 subspace

        Rp = Ud @ x + r_m  # Now Ud (L x d) @ x (d x N) is valid, then + r_m (L x 1)

        c = np.max(np.sqrt(np.sum(x**2, axis=0)))
        y = np.vstack([x, c * np.ones((1, N))])

        p_vca = d + 1

    else:  # SNR >= SNR_th
        if verbose == "on":
            print("... Select proj. to p-1")

        d = p

        try:
            Ud, Sd, Vd = sparse_svds(R @ R.T / N, k=d)
            idx_sorted = np.argsort(Sd)[::-1]
            Ud = Ud[:, idx_sorted]
        except Exception as e:
            warnings.warn(f"sparse_svds failed, falling back to full SVD: {e}")
            u_full, s_full, vh_full = np.linalg.svd(R @ R.T / N)
            Ud = u_full[:, :d]

        x = Ud.T @ R  # x_p in MATLAB, but assigned to x directly here
        Rp = Ud @ x  # No `+ r_m` here, as per MATLAB.

        u = np.mean(x, axis=1, keepdims=True)
        denominator_term = u.T @ x
        y = np.divide(
            x, denominator_term, out=np.zeros_like(x), where=denominator_term != 0
        )

        p_vca = p

    # VCA algorithm
    indice = np.zeros(p, dtype=int)
    A = np.zeros((p_vca, p))
    A[p_vca - 1, 0] = 1

    for i in range(p):
        w = np.random.rand(p_vca, 1)

        proj_A = A @ pinv(A)
        f = w - proj_A @ w

        f = f / np.linalg.norm(f)

        v = f.T @ y

        current_pixel_idx = np.argmax(np.abs(v))
        indice[i] = current_pixel_idx

        A[:, i] = y[:, current_pixel_idx]

    Ae = Rp[:, indice]

    return Ae, indice, Rp, SNR, Ud, x


def _compute_AtransYinvLA(Y, sinvl):
    """
    Compute A^T @ diag(sinvl) @ A where A = kron(Y.T, I_p), using column-major
    (Fortran-order) vectorization — faithful translation of computeAtransYinvLA.m.

    Parameters
    ----------
    Y : ndarray, shape (p, N)
    sinvl : ndarray, shape (p*N,)  — column-major flattened dual/slack product

    Returns
    -------
    AtransYinvLA : ndarray, shape (p^2, p^2)
    """
    p, N = Y.shape

    Yaug = np.zeros((p * p, N))
    SinvL = sinvl.reshape((p, N), order='F')          # (p, N)
    SinvLaug = np.tile(SinvL, (p, 1))                 # (p^2, N)

    for i in range(p):
        Yaug[i * p:(i + 1) * p, :] = np.tile(Y[i:i + 1, :], (p, 1))

    AtransYinvLcompact = Yaug * SinvLaug               # (p^2, N)
    AtransYinvLAcompact = AtransYinvLcompact @ Y.T     # (p^2, p)

    AtransYinvLA = np.zeros((p * p, p * p))
    for i in range(p):
        for k in range(p):
            for j in range(p):
                AtransYinvLA[i * p + k, k + j * p] = AtransYinvLAcompact[i * p + k, j]

    return AtransYinvLA


def _quad_prog1(G, c, Y, b, Aeq, beq, x0, throtle, verbose=0):
    """
    Interior-point primal-dual QP solver (Mehrotra predictor-corrector).

    Minimises  1/2 * x'Gx + c'x
    subject to  A*x >= b   (A = kron(Y.T, I_p), implicit via Y)
                Aeq*x = beq

    All vectors use column-major (Fortran) ordering consistent with MATLAB's
    column vectorisation Q(:).  Faithful translation of quadProg1.m.

    Parameters
    ----------
    G   : ndarray (p^2, p^2) — positive-definite quadratic coefficient
    c   : ndarray (p^2,)     — linear coefficient
    Y   : ndarray (p, N)     — data matrix (defines implicit A)
    b   : ndarray (p*N,)     — inequality RHS (zeros in MVSA)
    Aeq : ndarray (neq, p^2) — equality constraint matrix
    beq : ndarray (neq,)     — equality RHS
    x0  : ndarray (p^2,)     — warm-start point (column-major vec of Q0)
    throtle : bool           — slow-step flag from outer MVSA loop
    verbose : int            — 0 silent, >=2 print per-iteration info

    Returns
    -------
    x : ndarray (p^2,) — solution in column-major order
    """
    p, N = Y.shape
    neq = Aeq.shape[0]
    m = p * p
    n = N * p

    x = x0.copy()
    y_sl = np.ones(n)   # slacks  (y >= 0)
    l = np.ones(n)      # dual variables for inequalities
    mu_vec = np.ones(neq)

    Q_init = x0.reshape((p, p), order='F')
    previous = -np.log(np.abs(np.linalg.det(Q_init)))
    below_threshold = False

    nniter = 300 if throtle else 150

    for k in range(1, nniter + 1):
        yinvl = l / y_sl                                       # element-wise l/y

        # ---- Residuals ----
        temp = l.reshape((p, N), order='F') @ Y.T             # (p, p)
        rd = G @ x + c - temp.ravel(order='F') + Aeq.T @ mu_vec

        Qx = x.reshape((p, p), order='F') @ Y                 # (p, N)
        rb = Qx.ravel(order='F') - y_sl - b
        rbeq = Aeq @ x - beq

        # ---- Build augmented system ----
        AtYiLA = _compute_AtransYinvLA(Y, yinvl)
        K = G + AtYiLA
        Aug = np.block([[K, Aeq.T],
                        [Aeq, np.zeros((neq, neq))]])

        # ---- Affine (predictor) direction ----
        rh = yinvl * (rb + y_sl)
        rhaug1 = -rd - (rh.reshape((p, N), order='F') @ Y.T).ravel(order='F')
        rhaug = np.concatenate([rhaug1, -rbeq])

        try:
            DxDm = np.linalg.solve(Aug, rhaug)
        except np.linalg.LinAlgError:
            DxDm = np.linalg.lstsq(Aug, rhaug, rcond=None)[0]

        DxAff = DxDm[:m]
        DyAff = (DxAff.reshape((p, p), order='F') @ Y).ravel(order='F') + rb
        DlAff = -yinvl * (y_sl + DyAff)

        mi = float(y_sl @ l) / n

        neg_dy = DyAff < 0
        aDymin = float(np.min(-y_sl[neg_dy] / DyAff[neg_dy])) if np.any(neg_dy) else 1.0
        aDymin = min(aDymin, 1.0)
        neg_dl = DlAff < 0
        aDlmin = float(np.min(-l[neg_dl] / DlAff[neg_dl])) if np.any(neg_dl) else 1.0
        aDlmin = min(aDlmin, 1.0)
        aAff = min(aDymin, aDlmin)

        miAff = float((y_sl + aAff * DyAff) @ (l + aAff * DlAff)) / n
        mi_safe = max(mi, 1e-16)
        sigma = (miAff / mi_safe) ** 3

        # ---- Corrector direction ----
        ycorrected = y_sl + (DlAff * DyAff - sigma * mi_safe) / l
        rh2 = yinvl * (rb + ycorrected)
        rhaug1_2 = -rd - (rh2.reshape((p, N), order='F') @ Y.T).ravel(order='F')
        rhaug2 = np.concatenate([rhaug1_2, -rbeq])

        try:
            DxDm2 = np.linalg.solve(Aug, rhaug2)
        except np.linalg.LinAlgError:
            DxDm2 = np.linalg.lstsq(Aug, rhaug2, rcond=None)[0]

        Dx = DxDm2[:m]
        Dmu = DxDm2[m:]
        Dy = (Dx.reshape((p, p), order='F') @ Y).ravel(order='F') + rb
        Dl = -yinvl * (Dy + ycorrected)

        tk = 1.0 - 1.0 / (k + 1)

        neg_dy2 = Dy < 0
        apri = float(np.min(-tk * y_sl[neg_dy2] / Dy[neg_dy2])) if np.any(neg_dy2) else 1.0
        apri = min(apri, 1.0)
        neg_dl2 = Dl < 0
        adual = float(np.min(-tk * l[neg_dl2] / Dl[neg_dl2])) if np.any(neg_dl2) else 1.0
        adual = min(adual, 1.0)

        a = min(apri, adual)
        if throtle:
            a /= 10.0

        # ---- Update ----
        x_prev = x.copy()
        x = x + a * Dx
        Q_new = x.reshape((p, p), order='F')
        true_value_new = -np.log(np.abs(np.linalg.det(Q_new)))

        y_sl = y_sl + a * Dy
        l = l + a * Dl
        mu_vec = mu_vec + a * Dmu

        if verbose >= 2:
            print(f'    QP iter {k:3d}: f = {true_value_new:.4f}, '
                  f'sigma = {sigma:.2e}, mi = {mi:.2e}, a = {a:.4f}')

        if sigma < 1e-8 and mi < 1e-8:
            break

        if true_value_new < previous:
            previous = true_value_new
            below_threshold = True
        else:
            if below_threshold:
                x = x_prev   # revert to step before energy increased
                break

    return x


def mvsa(Y, p, MM_iters=10, spherize='yes', mu=1e-6, lambda_=1e-10,
         tol_f=1e-2, M0=None, verbose=1):
    """
    Minimum Volume Simplex Analysis (MVSA).

    Estimates the p endmember signatures M = [m_1, ..., m_p] forming the
    (p-1)-dimensional simplex of minimum volume that contains the data Y,
    under the linear mixing model  y_i = M @ x_i  where x_i is in the
    probability simplex.

    Implements the MM (majorisation-minimisation) sequence of quadratic
    sub-problems described in [1], [2].  Each QP is solved with a
    Mehrotra predictor-corrector interior-point method.

    Parameters
    ----------
    Y : ndarray, shape (L, N)
        Hyperspectral data matrix: L channels, N pixels.
    p : int
        Number of endmembers (simplex vertices).
    MM_iters : int, optional
        Maximum number of outer QP iterations.  Default: 10.
    spherize : str, optional
        'yes' applies a spherisation step so data spans equal range on
        every axis (improves conditioning).  Default: 'yes'.
    mu : float, optional
        Maximum eigenvalue of the quadratic regularisation term (mu*I)
        added to the Hessian.  Default: 1e-6.
    lambda_ : float, optional
        Regularisation parameter for the spherisation covariance.
        Default: 1e-10.
    tol_f : float, optional
        Relative tolerance for the outer termination test on f(Q).
        Default: 1e-2.
    M0 : ndarray or None, optional
        Initial endmember matrix, shape (L, p).  If None, VCA is used.
        Default: None.
    verbose : int, optional
        0 — silent; 1 — outer-loop messages; 2 — also QP inner messages.
        Default: 1.

    Returns
    -------
    M : ndarray, shape (L, p)
        Estimated endmember (mixing) matrix.
    Sest : ndarray, shape (p, N)
        Estimated source (abundance) matrix in the projected space,
        Sest = Q* @ Y_proj.
    Up : ndarray, shape (L, p)
        Isometric matrix spanning the identified p-dimensional subspace.
    my : ndarray, shape (L, 1)
        Data mean vector.
    sing_values : ndarray, shape (p-1,)
        Leading eigenvalues of the sample covariance (y-my)(y-my).T/N.

    References
    ----------
    [1] J. Li and J. M. Bioucas-Dias, "Minimum volume simplex analysis:
        A fast algorithm to unmix hyperspectral data," IGARSS 2008.
    [2] J. Li and J. M. Bioucas-Dias, "Minimum volume simplex analysis:
        A new algorithm to unmix hyperspectral data," IEEE TGRS, 2012.

    Original MATLAB authors: Jose Bioucas-Dias & Jun Li, 2009.
    Python translation from mvsa.m, quadProg1.m, computeAtransYinvLA.m.
    """
    Y = np.array(Y, dtype=float)
    L, N = Y.shape
    if L < p:
        raise ValueError('Insufficient number of rows in Y (L must be >= p)')

    slack = 1e-3
    any_energy_decreasing = False
    f_val_back = np.inf

    # ------------------------------------------------------------------ #
    #  1. Identify affine subspace (PCA, p-1 dims)                        #
    # ------------------------------------------------------------------ #
    my = np.mean(Y, axis=1, keepdims=True)          # (L, 1)
    Y = Y - my                                       # zero-mean

    # p-1 leading eigenvectors of the sample covariance
    # np.linalg.eigh returns eigenvalues ascending → reverse
    evals, evecs = np.linalg.eigh(Y @ Y.T / N)
    idx = np.argsort(evals)[::-1]
    Up = evecs[:, idx[:p - 1]]                       # (L, p-1)
    sing_values = evals[idx[:p - 1]]                 # (p-1,)
    D_diag = sing_values                             # alias for readability

    # Project onto (p-1)-subspace, then lift back
    Y = Up @ (Up.T @ Y)
    Y = Y + my                                       # lift

    # Orthogonal complement of my w.r.t. subspace
    my_ortho = my - Up @ (Up.T @ my)
    Up = np.hstack([Up, my_ortho / np.sqrt(np.sum(my_ortho ** 2))])  # (L, p)

    # Coordinates in R^p
    Y = Up.T @ Y                                     # (p, N)

    # ------------------------------------------------------------------ #
    #  2. Spherise (optional)                                             #
    # ------------------------------------------------------------------ #
    C = None
    if spherize == 'yes':
        Y_Ldim = Up @ Y - my                         # back to L-dim, centred
        C = np.diag(1.0 / np.sqrt(D_diag + lambda_))         # (p-1, p-1)
        Y_sph = C @ Up[:, :p - 1].T @ Y_Ldim         # (p-1, N)
        Y = np.vstack([Y_sph, np.ones((1, N))]) / np.sqrt(p)  # (p, N)

    # ------------------------------------------------------------------ #
    #  3. Initialise M                                                    #
    # ------------------------------------------------------------------ #
    if M0 is None:
        # VCA on the (spherised) projected data
        Mvca, _, _, _, _, _ = vca(Y, Endmembers=p)
        M = Mvca.copy()                              # (p, p)
        # Expand so initial Q = inv(M) is feasible
        Ym_col = np.mean(M, axis=1, keepdims=True)
        M = M + p * (M - Ym_col)
    else:
        M = np.array(M0, dtype=float)
        # Project M into the identified affine subspace
        M = M - my
        M = Up[:, :p - 1] @ (Up[:, :p - 1].T @ M)
        M = M + my
        M = Up.T @ M                                 # in R^p
        if spherize == 'yes':
            M_Ldim = Up @ M - my
            M_sph = C @ Up[:, :p - 1].T @ M_Ldim    # (p-1, p)
            M = np.vstack([M_sph, np.ones((1, p))]) / np.sqrt(p)

    Q = np.linalg.inv(M)

    # ------------------------------------------------------------------ #
    #  4. Build equality constraint for the QP                           #
    # ------------------------------------------------------------------ #
    # E @ vec(Q) = qm  enforces  ones(1,p) @ Q = qm  (column sums of Q)
    E = np.kron(np.eye(p), np.ones((1, p)))                  # (p, p^2)
    qm = np.sum(np.linalg.inv(Y @ Y.T) @ Y, axis=1)          # (p,)

    # ------------------------------------------------------------------ #
    #  5. MM outer loop                                                   #
    # ------------------------------------------------------------------ #
    throtle = False
    for k in range(1, MM_iters + 1):

        # ---- Make current M feasible (Q @ Y >= 0) ----
        M = np.linalg.inv(Q)
        Ym_col = np.mean(M, axis=1, keepdims=True)
        dW = M - Ym_col
        count = 0
        if not throtle:
            while np.any((Q @ Y) < 0):
                if verbose >= 1:
                    print(f'  iter {k}: expanding M to enforce feasibility...')
                M = M + 0.01 * dW
                Q = np.linalg.inv(M)
                count += 1
                if count > 100:
                    if verbose >= 1:
                        print(f'  iter {k}: could not make M feasible after 100 expansions')
                    break
        Q = np.linalg.inv(M)

        # ---- Gradient and Hessian of  -log|det(Q)|  at Q ----
        g = (-M.T).ravel(order='F')                  # (p^2,) gradient
        H_reg = mu * np.eye(p ** 2) + np.diag(g ** 2)
        q0 = Q.ravel(order='F')
        Q0 = Q.copy()
        f_lin = g - H_reg @ q0

        f0_val = -np.log(np.abs(np.linalg.det(Q0)))
        energy_decreasing = False

        # ---- Solve QP ----
        q = _quad_prog1(H_reg, f_lin, Y, np.zeros(p * N),
                        E, qm, q0, throtle, verbose=verbose)

        Q_cand = q.reshape((p, p), order='F')
        f_val = -np.log(np.abs(np.linalg.det(Q_cand)))

        if verbose >= 1:
            print(f'  iter {k}: f0 = {f0_val:.4f}, f = {f_val:.4f}')

        # ---- Accept / reject / throttle ----
        if f0_val < f_val:
            # Energy did not decrease → throttle or stop
            Q = Q0
            if throtle:
                break
            else:
                throtle = True
        else:
            throtle = False
            Q = Q_cand
            energy_decreasing = True
            any_energy_decreasing = True

        # ---- Termination test ----
        if energy_decreasing:
            if abs((f_val_back - f_val) / max(abs(f_val), 1e-16)) < tol_f and not throtle:
                if verbose >= 1:
                    print(f'  iter {k}: termination test PASSED')
                break
            f_val_back = f_val

    # ------------------------------------------------------------------ #
    #  6. Map Q back to endmember matrix in original space               #
    # ------------------------------------------------------------------ #
    if spherize == 'yes':
        M_out = np.linalg.inv(Q) * np.sqrt(p)       # unscale
        M_out = M_out[:p - 1, :]                     # remove lifted row
        M_out = Up[:, :p - 1] @ np.diag(np.sqrt(D_diag + lambda_)) @ M_out
        M_out = M_out + my                           # restore mean
    else:
        M_out = Up @ np.linalg.inv(Q)

    Sest = Q @ Y                                     # (p, N) abundances in proj. space

    return M_out, Sest, Up, my, sing_values


