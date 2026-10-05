"""
matching.py — column-wise alignment of endmember/archetype matrices and
permutation of cluster labels across runs.

`match_to_reference` is the similarity-based counterpart of the older
`match_endmembers` in tools.py (which uses scipy.spatial.distance.cdist).
Both solve the same Hungarian-assignment problem. The similarity driving the
assignment is pluggable (see `similarity_matrix`): cosine and Spearman on the
full loading columns, plus the top-weighted rank metrics prototyped in
notebook 08 — rank-biased overlap, weighted Kendall tau, and top-k Jaccard —
which emphasise the high-loading candidates that define an archetype.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import spearmanr
from sklearn.metrics.pairwise import cosine_similarity


def cosine_matrix(A, B):
    """Cosine similarity between the columns of two matrices.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype/endmember per column, sharing the row
        dimension (candidates).

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        ``C[i, j]`` is the cosine similarity of ``A[:, i]`` and ``B[:, j]``,
        in [-1, 1].
    """
    # sklearn expects rows as samples, so transpose column-major endmember matrices.
    return cosine_similarity(A.T, B.T)


def spearman_matrix(A, B):
    """Spearman rank correlation between the columns of two matrices.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column, sharing the row dimension.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        ``C[i, j]`` is the Spearman rho of ``A[:, i]`` vs ``B[:, j]``,
        in [-1, 1]. Every rank is weighted equally, so with many
        near-zero loadings the tail dominates; see the top-weighted
        alternatives below.
    """
    p_a = A.shape[1]
    rho = spearmanr(np.hstack([A, B]))[0]
    return np.atleast_2d(rho)[:p_a, p_a:]


def _cross_pairwise(A, B, f):
    """Apply a per-pair column function over the cross product of two matrices.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.
    f : callable
        ``f(col_a, col_b) -> float``, applied to every column pair.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        ``C[i, j] = f(A[:, i], B[:, j])``.
    """
    C = np.empty((A.shape[1], B.shape[1]))
    for i in range(A.shape[1]):
        for j in range(B.shape[1]):
            C[i, j] = f(A[:, i], B[:, j])
    return C


def _ranked_idx(col):
    """Candidate indices sorted by descending loading (as in notebook 08).

    Parameters
    ----------
    col : array-like, shape (L,)
        One archetype's loading column.

    Returns
    -------
    idx : ndarray, shape (L,)
        Indices such that ``col[idx]`` is non-increasing; ``idx[0]`` is the
        top-loading candidate.
    """
    return np.argsort(-np.asarray(col))


def rbo_ext(list_a, list_b, pval=0.9, k=None):
    """Extrapolated rank-biased overlap (Webber et al. 2010).

    Top-weighted agreement between two ranked lists: overlap is measured at
    every depth and discounted geometrically, so agreement near the top
    counts most. The "extrapolated" variant assumes the overlap fraction at
    the evaluated depth persists to infinity, keeping identical lists at 1.0.

    Parameters
    ----------
    list_a, list_b : sequence
        Ranked item lists, best first (e.g. candidate indices by descending
        loading). May differ in length; comparison stops at the shorter.
    pval : float, default 0.9
        Persistence parameter in (0, 1): the weight of depth d is
        ``pval ** d``. Smaller values are more top-heavy.
    k : int, optional
        If given, truncate both lists to their top k before comparing.

    Returns
    -------
    rbo : float
        Overlap score in [0, 1]; 1.0 for identical rankings.
    """
    if k:
        list_a, list_b = list_a[:k], list_b[:k]
    depth = min(len(list_a), len(list_b))
    sa, sb, rbo_sum, overlap = set(), set(), 0.0, 0
    for d in range(depth):
        sa.add(list_a[d]); sb.add(list_b[d])
        overlap = len(sa & sb)
        rbo_sum += (pval ** d) * (overlap / (d + 1))
    ext = (overlap / depth) * (pval ** depth)        # assume top-depth agreement persists
    return (1 - pval) * rbo_sum + ext


def weighted_tau_matrix(A, B):
    """Weighted Kendall tau between the columns of two matrices.

    Uses scipy's ``weightedtau`` with ``rank=True``: hyperbolic weights
    (exchanges near the top of the ranking cost more), symmetrised over
    which column serves as the ranker.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        Weighted tau of each column pair, in [-1, 1].
    """
    from scipy.stats import weightedtau
    return _cross_pairwise(A, B, lambda u, v: float(weightedtau(u, v, rank=True)[0]))


def rbo_matrix(A, B, pval=0.9):
    """Extrapolated rank-biased overlap between the columns of two matrices.

    Each column is converted to a descending-loading candidate ranking and
    pairs are scored with `rbo_ext`.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.
    pval : float, default 0.9
        RBO persistence parameter; see `rbo_ext`.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        RBO of each column pair, in [0, 1].
    """
    f = lambda u, v: rbo_ext(_ranked_idx(u).tolist(), _ranked_idx(v).tolist(), pval)
    return _cross_pairwise(A, B, f)


def topk_jaccard_matrix(A, B, k=12):
    """Jaccard overlap of the top-k candidate sets between columns.

    Order within the top-k set is ignored — this asks only "do the two
    archetypes headline the same candidates?". The default k = 12 matches
    the number of senate seats on a ballot.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.
    k : int, default 12
        How many top-loading candidates form each set.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        ``|top_k(a) & top_k(b)| / |top_k(a) | top_k(b)|`` for each column
        pair, in [0, 1].
    """
    def f(u, v):
        sa, sb = set(_ranked_idx(u)[:k]), set(_ranked_idx(v)[:k])
        return len(sa & sb) / len(sa | sb)
    return _cross_pairwise(A, B, f)


def cosine_topk_matrix(A, B, k=12):
    """Cosine similarity restricted to each pair's union of top-k candidates.

    The cosine of two loading columns evaluated only on the candidates that
    appear in either column's top-k, so the near-zero tail shared by all
    archetypes does not inflate the similarity (notebook 08's `m_cosine_top`).

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.
    k : int, default 12
        How many top-loading candidates per column enter the union.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        Cosine of each column pair on its top-k union, in [-1, 1].
    """
    def f(u, v):
        idx = np.union1d(_ranked_idx(u)[:k], _ranked_idx(v)[:k])
        a, b = u[idx], v[idx]
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    return _cross_pairwise(A, B, f)


_SIMILARITIES = {
    "cosine": cosine_matrix,
    "top12_cosine": cosine_topk_matrix,
    "spearman": spearman_matrix,
    "weighted_tau": weighted_tau_matrix,
    "rbo": rbo_matrix,
    "top12_jaccard": topk_jaccard_matrix,
}


def similarity_matrix(A, B, similarity="cosine"):
    """Column-similarity matrix between two archetype matrices.

    Parameters
    ----------
    A : ndarray, shape (L, p_A)
    B : ndarray, shape (L, p_B)
        Matrices with one archetype per column.
    similarity : {'cosine', 'top12_cosine', 'spearman', 'weighted_tau', 'rbo', 'top12_jaccard'} or callable
        Which metric to use (default 'cosine'). A callable receives
        ``(A, B)`` and must return the (p_A, p_B) similarity matrix.

    Returns
    -------
    C : ndarray, shape (p_A, p_B)
        Similarity of each column pair; higher means more alike.

    Raises
    ------
    ValueError
        If `similarity` is neither a registered name nor a callable.
    """
    f = _SIMILARITIES.get(similarity, similarity)
    if not callable(f):
        raise ValueError(f"similarity must be one of {sorted(_SIMILARITIES)} or a callable")
    return f(A, B)


def match_to_reference(M_ref, M_other, similarity="cosine"):
    """Hungarian alignment of `M_other` columns to `M_ref` columns by column similarity.

    Parameters
    ----------
    M_ref, M_other : ndarray, shape (L, p)
        Endmember matrices with one archetype per column.
    similarity : str or callable, default 'cosine'
        Column-similarity used for the assignment; any name registered in
        `similarity_matrix` ('cosine', 'spearman', 'weighted_tau', 'rbo',
        'top12_jaccard'), or a callable receiving ``(M_ref, M_other)`` and
        returning the (p, p) similarity matrix.

    Returns
    -------
    perm : ndarray, shape (p,)
        Permutation such that ``M_other[:, perm]`` best matches ``M_ref`` column-wise.
    matched_sim : ndarray, shape (p,)
        Similarity of each matched pair, in `M_ref`-column order.
    """
    C = similarity_matrix(M_ref, M_other, similarity)
    row_ind, col_ind = linear_sum_assignment(-C)   # maximise similarity
    perm = np.zeros(M_ref.shape[1], dtype=int)
    perm[row_ind] = col_ind
    matched_sim = C[row_ind, col_ind]
    return perm, matched_sim


def archetype_lineage(loadings_by_p):
    """Trace how archetypes split as the endmember count p increases.

    For each consecutive pair (p, p+1), the p+1 columns are Hungarian-matched
    to the p columns by cosine similarity; the one leftover column in p+1 is
    linked to its most similar parent and flagged as the "split" child.

    Parameters
    ----------
    loadings_by_p : dict[int, ndarray]
        {p: (L, p) consensus loading matrix}. Keys need not be contiguous;
        consecutive *available* p values are compared.

    Returns
    -------
    edges : list of dict with keys
        ``p_from``, ``k_from``, ``p_to``, ``k_to``, ``similarity``,
        ``split`` (True for the leftover child matched by max similarity).
    """
    edges = []
    ps = sorted(loadings_by_p)
    for p_from, p_to in zip(ps[:-1], ps[1:]):
        M_a = np.asarray(loadings_by_p[p_from])
        M_b = np.asarray(loadings_by_p[p_to])
        C = cosine_matrix(M_a, M_b)                    # (p_a, p_b)
        row_ind, col_ind = linear_sum_assignment(-C)   # matches min(p_a, p_b) pairs
        matched_children = set()
        for i, j in zip(row_ind, col_ind):
            edges.append({
                "p_from": p_from, "k_from": int(i),
                "p_to": p_to, "k_to": int(j),
                "similarity": float(C[i, j]), "split": False,
            })
            matched_children.add(int(j))
        for j in range(M_b.shape[1]):
            if j not in matched_children:
                parent = int(np.argmax(C[:, j]))
                edges.append({
                    "p_from": p_from, "k_from": parent,
                    "p_to": p_to, "k_to": j,
                    "similarity": float(C[parent, j]), "split": True,
                })
    return edges


def relabel_to_reference(ref, other, n_clusters):
    """Permute cluster labels so `other` overlaps `ref` as much as possible.

    Hungarian assignment on the label-overlap (contingency) matrix; requires
    both labelings to use the same number of clusters.

    Parameters
    ----------
    ref : array-like of int, shape (N,)
        Reference cluster label per sample, in ``0..n_clusters-1``.
    other : array-like of int, shape (N,)
        Labeling to relabel, same shape and label range as `ref`.
    n_clusters : int
        Number of clusters in both labelings.

    Returns
    -------
    relabeled : ndarray of int, shape (N,)
        `other` with labels permuted so cluster k maximally overlaps
        cluster k of `ref`.
    """
    C = np.zeros((n_clusters, n_clusters), dtype=int)
    for r, o in zip(ref, other):
        C[o, r] += 1
    row_ind, col_ind = linear_sum_assignment(-C)
    mapping = dict(zip(row_ind, col_ind))
    return np.array([mapping[o] for o in other])


def relabel_density_to_reference(ref, other, n_ref_clusters):
    """Align a density-clustering labeling (with noise) to a reference labeling.

    Like `relabel_to_reference`, but tolerant of the output shape of
    density-based clusterers: `other` may mark noise as -1 and may have a
    different number of non-noise clusters than the reference.

    Parameters
    ----------
    ref : array-like of int, shape (N,)
        Reference cluster label per sample, in ``0..n_ref_clusters-1``.
    other : array-like of int, shape (N,)
        Labeling to relabel; -1 marks noise, non-noise labels are arbitrary.
    n_ref_clusters : int
        Number of clusters in `ref`.

    Returns
    -------
    relabeled : ndarray of int, shape (N,)
        `other` with non-noise labels Hungarian-aligned to `ref` on the
        overlap matrix. Noise stays -1; extra clusters with no reference
        match get fresh labels ``>= n_ref_clusters``.
    """
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
