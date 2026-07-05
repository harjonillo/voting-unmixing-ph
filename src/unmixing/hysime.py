"""
hysime.py — Hyperspectral signal subspace estimation (HySime).

Translated from MATLAB hysime.m by Bioucas-Dias & Nascimento (2008).

Reference:
    J. Bioucas-Dias and J. Nascimento, "Hyperspectral subspace identification,"
    IEEE Transactions on Geoscience and Remote Sensing, vol. 46, no. 8,
    pp. 2435-2445, 2008.

  ┌──────────────┬──────────────────┬───────────────────────────────────────┐
  │   Concept    │  Hyperspectral   │               Your data               │   
  ├──────────────┼──────────────────┼───────────────────────────────────────┤   
  │ Band (L=4)   │ spectral channel │ candidate                             │   
  ├──────────────┼──────────────────┼───────────────────────────────────────┤   
  │ Pixel        │ spatial location │ precinct                              │   
  │ (N=5000)     │                  │                                       │
  ├──────────────┼──────────────────┼───────────────────────────────────────┤   
  │ Endmember    │ material         │ archetype party profile               │   
  │ (p=3)        │ spectrum         │                                       │
  ├──────────────┼──────────────────┼───────────────────────────────────────┤   
  │ kf           │ signal subspace  │ effective number of independent       │
  │              │ dim              │ archetypes                            │   
  ├──────────────┼──────────────────┼───────────────────────────────────────┤
  │ Ek (L×kf)    │ subspace basis   │ linear combinations of candidates     │
  │              │                  │ that capture variance                 │   
  ├──────────────┼──────────────────┼───────────────────────────────────────┤
  │ Ek.T @ y     │ projected coords │ each precinct's location in the       │   
  │              │                  │ archetype subspace                    │   
  └──────────────┴──────────────────┴───────────────────────────────────────┘
"""

import numpy as np


def hysime(y, w, Rw, verbose=True):
    """
    Estimate the signal subspace dimension and basis for hyperspectral data.

    Parameters
    ----------
    y : ndarray, shape (L, N)
        Hyperspectral data set. L = number of bands, N = number of pixels.
    w : ndarray, shape (L, N)
        Noise matrix (one noise vector per pixel), e.g. from est_noise().
    Rw : ndarray, shape (L, L)
        Noise correlation matrix, e.g. from est_noise().
    verbose : bool, optional
        Print progress messages. Default True.

    Returns
    -------
    kf : int
        Estimated signal subspace dimension.
    Ek : ndarray, shape (L, kf)
        Columns are the eigenvectors spanning the signal subspace.
    E : ndarray, shape (L, L)
        Complete orthonormal basis for R^L ordered by
        delta_p = Px(i) - Pn(i) (descending, i.e. most signal-dominant first).
    delta_p : ndarray, shape (L,)
        Per-eigenvector signal-minus-noise power differences (positive values
        correspond to signal-dominant directions).
    """
    y = np.array(y, dtype=float)
    w = np.array(w, dtype=float)
    Rw = np.array(Rw, dtype=float)

    L, N = y.shape

    if w.shape != (L, N):
        raise ValueError(
            f"Noise matrix shape {w.shape} does not match data shape {y.shape}."
        )

    d1, d2 = Rw.shape
    if d1 != d2 or d1 != L:
        print("Bad noise correlation matrix — recomputing from w.")
        Rw = w @ w.T / N

    # Signal estimate
    x = y - w

    if verbose:
        print("Computing the correlation matrices")

    Ry = y @ y.T / N     # sample correlation matrix
    Rx = x @ x.T / N     # signal correlation matrix estimate

    if verbose:
        print("Computing the eigenvectors of the signal correlation matrix")

    # SVD of Rx — for a PSD matrix, left singular vectors are eigenvectors.
    # np.linalg.svd returns singular values in *decreasing* order, matching
    # MATLAB's svd() behaviour.
    E, dx, _ = np.linalg.svd(Rx)   # E: (L, L),  dx: (L,) descending

    if verbose:
        print("Estimating the number of endmembers")

    # Regularise Rw slightly (equation before (23))
    Rw = Rw + np.sum(np.diag(Rx)) / L / 1e5 * np.eye(L)

    Py = np.diag(E.T @ Ry @ E)   # signal power per eigenvector  eq. (23)
    Pn = np.diag(E.T @ Rw @ E)   # noise  power per eigenvector  eq. (24)

    cost_F = -Py + 2.0 * Pn      # cost function                  eq. (22)

    kf = int(np.sum(cost_F < 0))

    # Sort ascending so the most signal-dominant directions come first
    ind_asc = np.argsort(cost_F)
    cost_F_ascend = cost_F[ind_asc]

    Ek = E[:, ind_asc[:kf]]
    E = E[:, ind_asc]

    if verbose:
        print(f"The signal subspace dimension is: k = {kf}")

    delta_p = -cost_F_ascend      # positive = signal dominates

    return kf, Ek, E, delta_p
