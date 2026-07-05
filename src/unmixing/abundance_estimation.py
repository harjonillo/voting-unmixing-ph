import numpy as np
from scipy.linalg import pinv
from scipy.optimize import nnls
import warnings


def ucls(Ae, R):
    # Unconstrained Least Squares (UCLS) — fast but may give negative values
    # Solves: R ≈ Ae @ abundances
    abundances = pinv(Ae) @ R  # shape: (p x N)

    return abundances


# Fully constrained: each pixel's abundances sum to 1 and are >= 0
def fcls(Ae, R):
    L, N = R.shape
    p = Ae.shape[1]

    # Augment to enforce sum-to-one constraint
    delta = 1e4  # regularization weight
    Ae_aug = np.vstack([Ae, delta * np.ones((1, p))])
    R_aug  = np.vstack([R,  delta * np.ones((1, N))])

    abundances = np.zeros((p, N))
    for j in range(N):
        abundances[:, j], _ = nnls(Ae_aug, R_aug[:, j])

    return abundances  # shape: (p x N)


def hyperFcls(Y_data, endmembers):
    """
    Fully Constrained Least Squares (FCLS) solver.
    This implementation is based on the iterative algorithm described in
    "Fully Constrained Least-Squares Based Linear Unmixing" by Heinz, Chang, and Althouse (1999),
    including a common correction to the sign in the formula.

    Solves for abundances (X) in Y = M @ X with:
    1. Non-negativity Constraint (ANC): X >= 0
    2. Abundance Sum-to-One Constraint (ASC): sum(X, axis=0) = 1

    Args:
        Y_data (np.ndarray): Hyperspectral data matrix (L channels x P pixels).
        endmembers (np.ndarray): Matrix of endmember signatures (L channels x R endmembers).

    Returns:
        np.ndarray: Abundance maps (R endmembers x P pixels), satisfying ANC and ASC.
    """
    # Input validation and dimension extraction
    if endmembers.ndim != 2:
        raise ValueError('Endmembers matrix (U) must be a 2D matrix (L x R).')

    L_data, P_pixels = Y_data.shape    # L = number of channels, P = number of pixels
    L_em, R_endmembers = endmembers.shape # L_em = channels, R = number of endmembers

    if L_data != L_em:
        raise ValueError('Y_data and endmembers must have the same number of spectral channels (L).')

    # Initialize abundance matrix X (R x P)
    X_abundances = np.zeros((R_endmembers, P_pixels))

    # Store a backup of the original endmembers matrix, as it will be modified in the loop
    endmembers_bckp = endmembers.copy()

    # Iterate over each pixel to solve for its abundances
    for p_idx in range(P_pixels):
        current_R = R_endmembers  # Number of endmembers currently considered for this pixel
        done = False              # Flag to indicate if solution is found for current pixel

        # `current_ref_indices` keeps track of the original indices of endmembers currently in `U_current`
        current_ref_indices = np.arange(R_endmembers)

        # `y_p` is the current pixel's spectrum (L x 1)
        y_p = Y_data[:, p_idx].reshape(-1, 1) # Ensure it's a column vector

        # `U_current` is the subset of endmembers currently being considered (L x current_R)
        U_current = endmembers_bckp.copy()

        # Iterative loop to enforce non-negativity
        while not done:
            # Calculate (U_current.T @ U_current)
            MTM = U_current.T @ U_current # (current_R x current_R)

            # Handle potential singularity or ill-conditioning
            if np.linalg.cond(MTM) > 1e10:
                warnings.warn("U.T @ U matrix is ill-conditioned during FCLS, adding regularization.")
                MTM = MTM + np.eye(current_R) * 1e-9 # Add small regularization

            try:
                MTM_inv = np.linalg.inv(MTM) # (current_R x current_R)
            except np.linalg.LinAlgError:
                warnings.warn("U.T @ U matrix is singular during FCLS, using pseudo-inverse. Results may be inaccurate.")
                MTM_inv = np.linalg.pinv(MTM) # Fallback to pseudo-inverse

            # 1. Unconstrained Least Squares (ALS) solution: als_hat = (U.T @ U)^-1 @ U.T @ r
            als_hat = MTM_inv @ U_current.T @ y_p # (current_R x 1)

            # 2. Vector 's' (sum-to-one constraint related term)
            # s = (U.T @ U)^-1 @ ones(count, 1)
            ones_vec = np.ones((current_R, 1)) # (current_R x 1)
            s = MTM_inv @ ones_vec # (current_R x 1)

            # 3. Fully Constrained Least Squares (FCLS) solution (intermediate step)
            # This implements the correction from the IEEE Magazine method.
            # afcls_hat = als_hat - inv(U.'*U)*ones(count, 1)*inv(ones(1, count)*inv(U.'*U)*ones(count, 1))*(ones(1, count)*als_hat-1);

            # (ones(1, count)*inv(U.'*U)*ones(count, 1)) is a scalar: ones_vec.T @ MTM_inv @ ones_vec
            scalar_denom = ones_vec.T @ MTM_inv @ ones_vec # (1 x 1)

            # Handle potential division by zero if scalar_denom is very small
            if np.abs(scalar_denom) < 1e-12:
                warnings.warn("Denominator for FCLS correction is near zero. Skipping correction for this pixel.")
                afcls_hat = als_hat # Fallback to ALS if correction term is unstable
            else:
                scalar_factor = np.linalg.inv(scalar_denom) # Inverse of the scalar (1x1)
                # (ones(1, count)*als_hat-1) is a scalar: ones_vec.T @ als_hat - 1
                scalar_term = (ones_vec.T @ als_hat - 1) # (1 x 1)

                afcls_hat = als_hat - s @ scalar_factor @ scalar_term # (current_R x 1)

            # Check if all components are positive. If so, then we found the solution.
            if np.all(afcls_hat >= -1e-9): # Use a small tolerance for "positive"
                alpha = np.zeros((R_endmembers, 1)) # Initialize full abundance vector
                alpha[current_ref_indices] = afcls_hat # Assign to original positions
                done = True # Solution found
                break # Exit inner while loop

            # If not all positive, find the most negative component to remove
            # Multiply negative elements by their counterpart in the s vector.
            # This step is part of the iterative removal process.
            idx_negative = np.where(afcls_hat < -1e-9)[0] # Indices of negative abundances

            # If no negative elements found but not all positive (e.g., due to tolerance),
            # this indicates a numerical issue or convergence problem.
            if len(idx_negative) == 0:
                warnings.warn("FCLS: No negative abundances found but not all positive (tolerance issue). Breaking loop.")
                alpha = np.zeros((R_endmembers, 1))
                alpha[current_ref_indices] = afcls_hat # Assign current best estimate
                done = True
                break

            # Calculate a ratio for negative elements (as per original algorithm)
            # Find largest abs(a_ij, s_ij) and remove entry from alpha.
            # The original MATLAB code implies `afcls_hat(idx) ./ s(idx)` is used to find the most negative.
            ratios = afcls_hat[idx_negative] / s[idx_negative]

            # Find the index (within idx_negative) of the maximum ratio (most negative contribution)
            max_ratio_idx_in_negative = np.argmax(np.abs(ratios))

            # Get the original index of the endmember to remove
            idx_to_remove_in_current_U = idx_negative[max_ratio_idx_in_negative]

            # Remove this endmember from the current set
            keep_indices_in_current_U = np.setdiff1d(np.arange(current_R), idx_to_remove_in_current_U)

            U_current = U_current[:, keep_indices_in_current_U]
            current_R -= 1 # Decrement count of active endmembers
            current_ref_indices = current_ref_indices[keep_indices_in_current_U] # Update reference indices

            if current_R == 0: # All endmembers removed, no solution possible
                warnings.warn(f"FCLS: All endmembers removed for pixel {p_idx}. Abundances set to zero.")
                alpha = np.zeros((R_endmembers, 1))
                done = True
                break

        # Assign the calculated abundances for the current pixel
        # Ensure alpha is a 1D array before assigning to X_abundances column
        X_abundances[:, p_idx] = alpha.flatten()

    return X_abundances


def sunsal_mod(M, y, AL_iters=1000, lambda_=0.0, positivity='no', threshold=0.0,
               addone='no', tol=1e-4, verbose='no', x0=None):
    """
    SUNSAL_MOD - Sparse Unmixing via variable Splitting and Augmented Lagrangian (modified).

    Solves the l2-l1 optimization problem:

        min  (1/2) ||M X - y||^2_F + lambda ||X||_1
         X

    Optionally subject to:
        1) POSITIVITY:  X >= threshold
        2) ADDONE:      sum(X) = ones(1, N)

    Uses variable splitting and the Alternating Direction Method of Multipliers (ADMM).

    Parameters
    ----------
    M : ndarray, shape (L, p)
        Mixing matrix with L channels and p endmembers.
    y : ndarray, shape (L, N)
        Data matrix with L channels and N pixels.
    AL_iters : int, optional
        Maximum number of augmented Lagrangian iterations. Default: 1000.
    lambda_ : float or ndarray, optional
        Regularization parameter. Scalar or 1-D array of length N (one per pixel).
        Default: 0.0.
    positivity : str, optional
        'yes' enforces X >= threshold. Default: 'no'.
    threshold : float, optional
        Lower bound used when positivity='yes'. Default: 0.0.
    addone : str, optional
        'yes' enforces sum(X) = 1 for each pixel. Default: 'no'.
    tol : float, optional
        Convergence tolerance for primal and dual residuals. Default: 1e-4.
    verbose : str, optional
        'yes' prints iteration info. Default: 'no'.
    x0 : ndarray or None, optional
        Initial solution, shape (p, N). Default: None (warm-started from least squares).

    Returns
    -------
    z : ndarray, shape (p, N)
        Estimated abundance matrix.
    res_p : float
        Final primal residual.
    res_d : float
        Final dual residual.

    References
    ----------
    J. Bioucas-Dias and M. Figueiredo, "Alternating direction algorithms for
    constrained sparse regression: Application to hyperspectral unmixing",
    2nd IEEE GRSS Workshop on Hyperspectral Image and Signal Processing
    (WHISPERS'2010), Reykjavik, Iceland, 2010.

    Original MATLAB author: Jose Bioucas-Dias, 2009
    Python translation from sunsal_mod.m
    """

    LM, p = M.shape
    L, N = y.shape

    if LM != L:
        raise ValueError('Mixing matrix M and data set y are inconsistent')

    # --- Expand lambda to (p, N) ---
    lambda_ = np.asarray(lambda_, dtype=float)
    if lambda_.ndim == 0:
        lambda_ = float(lambda_) * np.ones((p, N))
    elif lambda_.ndim == 1:
        if lambda_.size != N:
            raise ValueError('Lambda size is inconsistent with the size of the data set')
        lambda_ = np.tile(lambda_.reshape(1, N), (p, 1))

    # Rescale M, y, and lambda by the RMS of y
    norm_y = np.sqrt(np.mean(y ** 2))
    M = M / norm_y
    y = y / norm_y
    lambda_ = lambda_ / norm_y ** 2

    # --- Pure least squares (no regularisation, no constraints) ---
    if np.all(lambda_ == 0) and positivity == 'no' and addone == 'no':
        z = np.linalg.pinv(M) @ y
        return z, 0.0, 0.0

    # --- Constrained least squares: sum-to-one only, no positivity ---
    SMALL = 1e-12
    B = np.ones((1, p))   # (1, p)
    a = np.ones((1, N))   # (1, N)

    if addone == 'yes' and positivity == 'no':
        F = M.T @ M
        # rcond(F) > SMALL in MATLAB ↔ condition number is not too large
        if 1.0 / np.linalg.cond(F) > SMALL:
            IF = np.linalg.inv(F)
            BIFB_inv = np.linalg.inv(B @ IF @ B.T)
            z = IF @ M.T @ y - IF @ B.T @ BIFB_inv @ (B @ IF @ M.T @ y - a)
            return z, 0.0, 0.0

    # --- ADMM setup ---
    mu_AL = 0.01
    mu = 10 * float(np.mean(lambda_)) + mu_AL

    # Eigendecomposition of M'M for efficient updates
    UF, sF, _ = np.linalg.svd(M.T @ M)   # sF is 1-D array of singular values

    def _build_IF(mu_val):
        IF = UF @ np.diag(1.0 / (sF + mu_val)) @ UF.T
        Aux = IF @ B.T @ np.linalg.inv(B @ IF @ B.T)
        x_aux = Aux @ a
        IF1 = IF - Aux @ B @ IF
        return IF, x_aux, IF1

    IF, x_aux, IF1 = _build_IF(mu)
    yy = M.T @ y   # (p, N)

    # --- Initial solution ---
    if x0 is None:
        x = IF @ yy
    else:
        if x0.shape != (p, N):
            raise ValueError('Initial X is inconsistent with M or Y')
        x = x0.copy()

    z = x.copy()
    d = np.zeros_like(z)

    # --- ADMM iterations ---
    tol1 = np.sqrt(N * p) * tol
    tol2 = np.sqrt(N * p) * tol
    res_p = np.inf
    res_d = np.inf
    z0 = z.copy()
    mu_changed = False

    def _soft(x, t):
        """Element-wise soft-thresholding."""
        return np.sign(x) * np.maximum(np.abs(x) - t, 0.0)

    use_soft = np.any(lambda_ > 0)

    for i in range(1, AL_iters + 1):
        if abs(res_p) <= tol1 and abs(res_d) <= tol2:
            break

        # Save z for dual residual every 10 iterations (MATLAB: mod(i,10)==1)
        if i % 10 == 1:
            z0 = z.copy()

        # Z-update
        if use_soft:
            z = _soft(x - d, lambda_ / mu)
        else:
            z = x - d   # soft(x, 0) = x

        if positivity == 'yes':
            z = np.maximum(z, threshold)

        # X-update
        if addone == 'yes':
            x = IF1 @ (yy + mu * (z + d)) + x_aux
        else:
            x = IF @ (yy + mu * (z + d))

        # Dual variable update
        d = d - (x - z)

        # Residuals and mu adaptation (every 10 iterations)
        if i % 10 == 1:
            res_p = np.linalg.norm(x - z, 'fro')
            res_d = mu * np.linalg.norm(z - z0, 'fro')

            if verbose == 'yes':
                print(f' i = {i}, res_p = {res_p:.6f}, res_d = {res_d:.6f}')

            if res_p > 10 * res_d:
                mu *= 2
                d /= 2
                mu_changed = True
            elif res_d > 10 * res_p:
                mu /= 2
                d *= 2
                mu_changed = True

            if mu_changed:
                IF, x_aux, IF1 = _build_IF(mu)
                mu_changed = False

    return z, res_p, res_d
