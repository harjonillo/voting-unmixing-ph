"""
est_noise.py — Hyperspectral noise estimation.

Translated from MATLAB estNoise.m by Bioucas-Dias & Nascimento (2008).

Reference:
    J. Bioucas-Dias and J. Nascimento, "Hyperspectral subspace identification,"
    IEEE Transactions on Geoscience and Remote Sensing, vol. 46, no. 8,
    pp. 2435-2445, 2008.
"""

import numpy as np


def est_noise(y, noise_type="additive", verbose=True):
    """
    Estimate noise in a hyperspectral data set.

    Models each band's reflectance as a linear regression on the remaining
    bands to infer per-pixel noise.

    Parameters
    ----------
    y : ndarray, shape (L, N)
        Hyperspectral data set. L = number of bands, N = number of pixels.
    noise_type : str, optional
        'additive' (default) or 'poisson'.
    verbose : bool, optional
        Print progress messages. Default True.

    Returns
    -------
    w : ndarray, shape (L, N)
        Noise estimates for every pixel.
    Rw : ndarray, shape (L, L)
        Diagonal noise correlation matrix estimate.
    """
    y = np.array(y, dtype=float)
    L, N = y.shape
    if L < 2:
        raise ValueError("Too few bands to estimate the noise.")

    if verbose:
        print("Noise estimates:")

    if noise_type == "poisson":
        sqy = np.sqrt(np.maximum(y, 0))       # prevent negative values
        u, Ru = _est_additive_noise(sqy, verbose)
        x = (sqy - u) ** 2                     # signal estimates
        w = np.sqrt(x) * u * 2
        Rw = w @ w.T / N
    else:  # additive
        w, Rw = _est_additive_noise(y, verbose)

    return w, Rw


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _est_additive_noise(r, verbose=True):
    """
    Estimate additive noise via band-wise linear regression.

    Parameters
    ----------
    r : ndarray, shape (L, N)
    verbose : bool

    Returns
    -------
    w : ndarray, shape (L, N)   — noise estimates
    Rw : ndarray, shape (L, L)  — diagonal noise correlation matrix
    """
    small = 1e-6
    L, N = r.shape

    w = np.zeros((L, N))

    if verbose:
        print("  Computing sample correlation matrix and its inverse")

    RR = r @ r.T                              # (L, L)  equation (11)
    RRi = np.linalg.inv(RR + small * np.eye(L))  # equation (11)

    if verbose:
        print("  Computing band: ", end="", flush=True)

    for i in range(L):
        if verbose:
            print(f"\b\b\b{i+1:3d}", end="", flush=True)

        # equation (14): rank-1 update of RRi
        XX = RRi - np.outer(RRi[:, i], RRi[i, :]) / RRi[i, i]

        RRa = RR[:, i].copy()
        RRa[i] = 0.0                          # remove effect of XX[:, i]

        # equation (9)
        beta = XX @ RRa
        beta[i] = 0.0                         # remove effect of XX[i, :]

        # equation (10)
        w[i, :] = r[i, :] - beta @ r          # beta[i]=0 so band i cancels

    if verbose:
        print("\n  Computing noise correlation matrix")

    Rw = np.diag(np.diag(w @ w.T / N))

    return w, Rw
