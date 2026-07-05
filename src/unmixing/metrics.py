import numpy as np


def resolution(k_s):
    """
    k_s: array-like, number of inputs that correspond to a state s
    """
    M = np.sum(k_s)
    return -np.sum((k_s / M) * np.log(k_s / M))


def relevance(m_k, k_s):
    """
    m_k: array-like, number of states with energy E = −log(k/M)
    k_s: array-like, number of inputs that correspond to a state s

    TODO: formula is incomplete — the variable `k` (the energy level index)
    is not defined. See Marsili et al. for the intended Zipf-Mandelbrot form.
    """
    raise NotImplementedError(
        "relevance() is not yet implemented: the variable `k` in the summation "
        "is undefined. Please complete the formula before using this function."
    )