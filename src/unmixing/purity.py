"""Pixel purity checks taken from the unmixing literature (notebook 11).

Two measures, both relative to an *estimated* simplex (endmembers ``M``), not
the true one:

- ``outside_simplex`` — the check Li et al. (2015, Sec. V) run on the Cuprite
  scene: given an estimated simplex, count the samples outside it.
- ``purity`` — the purity of a pixel as Li et al. (2015, Sec. IV-B, after
  Berman et al. 2004) define it: its maximum abundance fraction.

References
----------
J. Li, A. Agathos, D. Zaharie, J. M. Bioucas-Dias, A. Plaza and X. Li,
"Minimum volume simplex analysis: A fast algorithm for linear hyperspectral
unmixing," IEEE TGRS 53(9):5067-5082, 2015.
J. M. P. Nascimento and J. M. Bioucas-Dias, "Vertex component analysis: A fast
algorithm to unmix hyperspectral data," IEEE TGRS 43(4):898-910, 2005.
"""

from __future__ import annotations

import numpy as np

from .abundance_estimation import sunsal_mod

# Purity caps the papers use to build data without pure pixels: 0.8 in Li &
# Bioucas-Dias (2008, Sec. 3) and Li et al. (2015, Sec. IV-B); 0.6 follows from
# Nascimento & Bioucas-Dias (2005, Sec. III), who reject every pixel with an
# abundance below 0.2 at p = 3.
PURITY_CAPS = (0.8, 0.6)

# Float tolerance only: the paper gives no tolerance for "outside".
OUTSIDE_TOL = 1e-8

# Purity thresholds for the site's "precincts at or above a purity" curves. A
# sample counts when its purity is at least the threshold, within THRESHOLD_TOL
# (SUNSAL abundances reach 1 only to solver precision).
PURITY_THRESHOLDS = tuple(round(0.05 * i, 2) for i in range(21))
THRESHOLD_TOL = 1e-6


def outside_simplex(M: np.ndarray, Y: np.ndarray, tol: float = OUTSIDE_TOL) -> dict:
    """Number of samples outside the simplex spanned by the columns of `M`.

    Li et al. (2015, Sec. V): "given an estimated simplex, the large majority
    of the spectral vectors are outside of that simplex", read there as a
    symptom that the data do not meet the minimum-volume assumption.

    A sample is outside when its abundance vector under the sum-to-one
    constraint alone (no sign constraint) has a negative entry.

    Parameters
    ----------
    M : ndarray, shape (L, p)
        Endmembers.
    Y : ndarray, shape (L, N)
        Data, one sample (precinct) per column.
    tol : float
        An entry counts as negative below ``-tol``.

    Returns
    -------
    dict
        ``n_outside`` (int) and ``share_outside`` (float).
    """
    A_free, _, _ = sunsal_mod(M, Y, positivity="no", addone="yes", verbose="no")
    outside = (A_free < -tol).any(axis=0)
    return {
        "n_outside": int(outside.sum()),
        "share_outside": float(outside.mean()),
    }


def purity(A: np.ndarray, caps: tuple = PURITY_CAPS) -> dict:
    """Maximum-abundance purity of the samples, per dominant endmember.

    Li et al. (2015, Sec. IV-B): the purity of a pixel is its maximum abundance
    fraction; a data set has "maximum purity" 1 when every endmember has a pure
    pixel, and 0.8 when every pixel with a larger abundance is discarded.

    Parameters
    ----------
    A : ndarray, shape (p, N)
        Abundances (non-negative, summing to one per column).
    caps : tuple of float
        Purity levels to count samples above.

    Returns
    -------
    dict
        ``max_purity`` : ndarray (p,), the largest purity among the samples
        endmember j dominates (NaN when it dominates none), and
        ``n_above_<cap>`` : ndarray (p,) of ints, how many of them exceed `cap`.
    """
    p = A.shape[0]
    pur = A.max(axis=0)
    dom = A.argmax(axis=0)
    out = {"max_purity": np.full(p, np.nan)}
    for j in range(p):
        if (dom == j).any():
            out["max_purity"][j] = pur[dom == j].max()
    for cap in caps:
        out[f"n_above_{cap:g}"] = np.bincount(dom[pur > cap], minlength=p)
    return out


def purity_counts(
    A: np.ndarray, thresholds: tuple = PURITY_THRESHOLDS, tol: float = THRESHOLD_TOL
) -> list[int]:
    """Number of samples whose purity (maximum abundance) is at least each of
    `thresholds`, within `tol`.

    Parameters
    ----------
    A : ndarray, shape (p, N)
        Abundances.
    """
    pur = A.max(axis=0)
    return [int((pur >= th - tol).sum()) for th in thresholds]
