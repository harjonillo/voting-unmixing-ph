"""
matching.py — column-wise alignment of endmember/archetype matrices and
permutation of cluster labels across runs.

`match_to_reference` is the cosine-similarity counterpart of the older
`match_endmembers` in tools.py (which uses scipy.spatial.distance.cdist).
Both solve the same Hungarian-assignment problem; the cosine version is
preferred for archetype matrices since column scale is irrelevant.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics.pairwise import cosine_similarity


def cosine_matrix(A, B):
    """p_A x p_B cosine similarity between the columns of A and B."""
    # sklearn expects rows as samples, so transpose column-major endmember matrices.
    return cosine_similarity(A.T, B.T)


def match_to_reference(M_ref, M_other):
    """Hungarian alignment of `M_other` columns to `M_ref` columns by cosine similarity.

    Parameters
    ----------
    M_ref, M_other : ndarray, shape (L, p)
        Endmember matrices with one archetype per column.

    Returns
    -------
    perm : ndarray, shape (p,)
        Permutation such that ``M_other[:, perm]`` best matches ``M_ref`` column-wise.
    matched_sim : ndarray, shape (p,)
        Cosine similarity of each matched pair, in `M_ref`-column order.
    """
    C = cosine_matrix(M_ref, M_other)
    row_ind, col_ind = linear_sum_assignment(-C)   # maximise similarity
    perm = np.zeros(M_ref.shape[1], dtype=int)
    perm[row_ind] = col_ind
    matched_sim = C[row_ind, col_ind]
    return perm, matched_sim


def relabel_to_reference(ref, other, n_clusters):
    """Permute `other` cluster labels via Hungarian so cluster k of `other` overlaps
    cluster k of `ref` as much as possible. Requires equal cluster counts."""
    C = np.zeros((n_clusters, n_clusters), dtype=int)
    for r, o in zip(ref, other):
        C[o, r] += 1
    row_ind, col_ind = linear_sum_assignment(-C)
    mapping = dict(zip(row_ind, col_ind))
    return np.array([mapping[o] for o in other])


def relabel_density_to_reference(ref, other, n_ref_clusters):
    """Relabel `other` (may include noise = -1 and have != n_ref_clusters non-noise
    clusters) so its non-noise labels align to `ref` via Hungarian on the overlap
    matrix. Noise stays -1. Unmatched extra clusters get labels >= n_ref_clusters."""
    mask = other >= 0
    uniq = sorted(np.unique(other[mask]).tolist())
    C = np.zeros((len(uniq), n_ref_clusters), dtype=int)
    for r, o in zip(ref[mask], other[mask]):
        C[uniq.index(o), r] += 1
    row_ind, col_ind = linear_sum_assignment(-C)
    mapping = {uniq[i]: int(c) for i, c in zip(row_ind, col_ind)}
    extra = n_ref_clusters
    for u in uniq:
        if u not in mapping:
            mapping[u] = extra
            extra += 1
    return np.array([mapping[o] if o >= 0 else -1 for o in other])
