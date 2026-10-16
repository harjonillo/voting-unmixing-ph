import numpy as np
from numpy.typing import ArrayLike


def resolution(k_s: ArrayLike) -> float:
    """
    Shannon entropy of the empirical state distribution (resolution).

    Following Marsili et al., the resolution of a sample is the entropy
    of the frequencies with which each state s is observed:
    H = -sum_s (k_s / M) log(k_s / M), where M = sum_s k_s.

    Parameters
    ----------
    k_s : array-like, shape (n_states,)
        Number of inputs (samples) that correspond to each state s.
        All entries must be positive.

    Returns
    -------
    float
        Resolution H[s] in nats.
    """
    M = np.sum(k_s)
    return -np.sum((k_s / M) * np.log(k_s / M))


def relevance(m_k: ArrayLike, k_s: ArrayLike) -> float:
    """
    Relevance H[k] of a sample (NOT YET IMPLEMENTED).

    Parameters
    ----------
    m_k : array-like
        Number of states with energy E = -log(k/M).
    k_s : array-like, shape (n_states,)
        Number of inputs (samples) that correspond to each state s.

    Returns
    -------
    float
        Relevance H[k] in nats (once implemented).

    Raises
    ------
    NotImplementedError
        Always. The variable ``k`` (the energy level index) in the
        summation is undefined; see Marsili et al. for the intended
        Zipf-Mandelbrot form.
    """
    raise NotImplementedError(
        "relevance() is not yet implemented: the variable `k` in the summation "
        "is undefined. Please complete the formula before using this function."
    )
