import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from typing import List, Union, Optional, Dict, Tuple
import warnings

from src.unmixing.endmember_extraction import vca


def match_endmembers(
    y_true: np.ndarray,
    y_extracted: np.ndarray,
    metric: str = "euclidean",
    algo: str = "linear_sum",
) -> List[int]:
    """
    Match extracted endmembers to true endmembers..

    Parameters:
    - y_true: np.ndarray of shape (n_endmembers, n_bands)
    - y_extracted: np.ndarray of shape (n_endmembers, n_bands)

    Returns:
    - matched_indices: list of indices indicating the best match of extracted to true endmembers
    """

    # Compute the cost matrix based on Euclidean distance
    cost_matrix = cdist(y_true, y_extracted, metric=metric)

    if algo == "min":
        col_ind = np.argmin(cost_matrix, axis=1)

    if algo == "linear_sum":
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

    return col_ind


def plot_elbow(Y_mixed: np.ndarray, endmember_range: Union[List[int], np.ndarray]):
    """
    :param Y_mixed: DataFrame of vote fractions (candidates x precincts)
    :param endmember_range: List of integers representing the range of endmembers to test
    """
    # TODO: allow choice of metric (rss, snr)
    rss_values = []
    snr_values = []

    for n in endmember_range:
        endm_vca, indices_vca, Rp_vca, SNR, Ud, x = vca(
            Y_mixed, Endmembers=int(n), verbose="on"
        )
        # TODO: get only the top candidates before computing RSS
        #  but first the noise floor must be established
        Y_rec = Rp_vca.copy()
        rss = np.sum((Y_mixed - Y_rec) ** 2)

        rss_values.append(rss)
        snr_values.append(SNR)

    fig, axs = plt.subplots(1, 2, figsize=(8, 5))
    axs[0].plot(endmember_range, rss_values, marker="o")
    axs[0].set_title("Elbow Plot: RSS vs Number of Endmembers")
    axs[0].set_xlabel("Number of Endmembers")
    axs[0].set_ylabel("Residual Sum of Squares (RSS)")
    axs[0].set_xticks(endmember_range)
    axs[0].grid(True)

    axs[1].plot(endmember_range, snr_values, marker="o")
    axs[1].set_title("Elbow Plot: SNR vs Number of Endmembers")
    axs[1].set_xlabel("Number of Endmembers")
    axs[1].set_ylabel("Signal-to-noise Ratio (SNR)")
    axs[1].set_xticks(endmember_range)
    axs[1].grid(True)


# ---------------------------------------------------------------------------
# Endmember noise-floor analysis
# ---------------------------------------------------------------------------


def endmember_noise_floor(
    M: np.ndarray,
    candidate_labels: Optional[List[str]] = None,
    cumulative_threshold: float = 0.95,
    cross_archetype_sigma: float = 2.0,
    plot: bool = True,
) -> Dict[str, object]:
    """
    Determine which candidates carry meaningful weight in each extracted
    archetype (endmember) and which are indistinguishable from noise.

    Two complementary diagnostics are computed per archetype column of M:

    1.  **Cumulative weight threshold** — candidates are sorted by their
        absolute loading; the function reports how many are needed to reach
        ``cumulative_threshold`` of the total weight.

    2.  **Cross-archetype comparison** — for each candidate i in archetype
        j, the candidate's normalised loading is compared against its mean
        and SD across the *other* p-1 archetypes.  A candidate is flagged
        as signal if its loading in archetype j exceeds its cross-archetype
        mean by ``cross_archetype_sigma`` standard deviations.

        This is more appropriate than a global z-score (which assumes a
        symmetric Dirichlet null) because it calibrates each candidate's
        threshold to *that candidate's own baseline* across archetypes.
        A universally popular candidate will have a high mean everywhere,
        so they need an even higher loading in archetype j to qualify as
        archetype-specific signal.

        When p < 3 (only 1 comparison value available), a warning is
        issued and signal detection falls back to comparing against the
        uniform expectation 1/L, since there is insufficient data for
        a meaningful cross-archetype SD.

    Parameters
    ----------
    M : ndarray, shape (L, p)
        Endmember (mixing) matrix produced by MVSA / VCA.
        L = number of candidates, p = number of archetypes.
        Each column is one archetype's signature over all candidates.
    candidate_labels : list of str, optional
        Human-readable names for the L candidates.  If None, integer
        indices are used.
    cumulative_threshold : float, optional
        Fraction of total archetype weight used to define the
        "effective archetype size" (default 0.95).
    cross_archetype_sigma : float, optional
        Number of standard deviations above the cross-archetype mean
        required to classify a candidate as signal (default 2.0).
    plot : bool, optional
        If True, produce a per-archetype diagnostic figure (default True).

    Returns
    -------
    results : dict with keys

        ``"M_normed"`` : ndarray, shape (L, p), column-normalised
                         absolute endmember matrix (each column sums to 1).

        ``"archetypes"`` : list of dicts (one per archetype), each with:

            ``"archetype_idx"``     — int, column index in M.

            ``"sorted_candidates"`` — ndarray of candidate indices sorted
                                      by descending loading magnitude.

            ``"sorted_labels"``     — list of str labels in the same order.

            ``"sorted_weights"``    — ndarray of normalised loadings (sorted
                                      descending).

            ``"cumulative_frac"``   — ndarray of cumulative weight fractions.

            ``"n_effective"``       — int, number of candidates needed to
                                      reach ``cumulative_threshold``.

            ``"cross_mean"``        — ndarray (L,), per-candidate mean of
                                      normalised loading across other
                                      archetypes (original candidate order).

            ``"cross_std"``         — ndarray (L,), per-candidate SD across
                                      other archetypes (original order).

            ``"cross_sigma"``       — ndarray (L,), number of SDs the
                                      loading in this archetype exceeds the
                                      cross-archetype mean (original order).

            ``"cross_signal"``      — boolean ndarray (L,), True where
                                      cross_sigma > ``cross_archetype_sigma``
                                      (original candidate order).

        ``"summary"`` : ndarray of shape (p,), the ``n_effective`` per
                        archetype — a quick-look vector.
    """
    M = np.asarray(M, dtype=float)
    if M.ndim != 2:
        raise ValueError(f"M must be 2-D, got shape {M.shape}")

    L, p = M.shape

    if candidate_labels is None:
        candidate_labels = [str(i) for i in range(L)]
    if len(candidate_labels) != L:
        raise ValueError(
            f"candidate_labels length ({len(candidate_labels)}) != L ({L})"
        )

    uniform_expectation = 1.0 / L

    # Normalise ALL columns: absolute value, each column sums to 1
    M_abs = np.abs(M)
    col_sums = M_abs.sum(axis=0)
    col_sums[col_sums < 1e-15] = 1.0
    M_normed = M_abs / col_sums[np.newaxis, :]  # (L, p)

    if p < 3:
        warnings.warn(
            f"Only {p} archetypes — cross-archetype SD is unreliable "
            f"(only {p - 1} comparison values per candidate). "
            f"Signal detection falls back to comparison against 1/L."
        )

    archetype_results = []

    for j in range(p):
        normed = M_normed[:, j]  # (L,) this archetype

        # ── 1. Cumulative weight ──────────────────────────────────────
        sort_idx = np.argsort(normed)[::-1]
        sorted_weights = normed[sort_idx]
        cumfrac = np.cumsum(sorted_weights)

        n_eff = int(np.searchsorted(cumfrac, cumulative_threshold) + 1)
        n_eff = min(n_eff, L)

        sorted_labels = [candidate_labels[i] for i in sort_idx]

        # ── 2. Cross-archetype comparison ─────────────────────────────
        other_cols = np.delete(M_normed, j, axis=1)  # (L, p-1)

        cross_mean = other_cols.mean(axis=1)          # (L,)
        if p >= 3:
            # ddof=1 for sample SD with p-1 >= 2 values
            cross_std = other_cols.std(axis=1, ddof=1)  # (L,)
        else:
            # With only 1 comparison value, SD is undefined.
            # Use a small epsilon so we don't divide by zero;
            # signal detection will rely on distance from 1/L instead.
            cross_std = np.full(L, np.nan)

        # How many SDs above the cross-archetype mean?
        if p >= 3:
            safe_std = np.where(cross_std > 1e-15, cross_std, 1e-15)
            cross_sigma = (normed - cross_mean) / safe_std
        else:
            # Fallback: measure distance from uniform in units of the
            # cross-archetype range (max - min across all archetypes)
            global_range = M_normed.max(axis=1) - M_normed.min(axis=1)
            safe_range = np.where(global_range > 1e-15, global_range, 1e-15)
            cross_sigma = (normed - uniform_expectation) / safe_range

        cross_signal = cross_sigma > cross_archetype_sigma

        archetype_results.append(
            {
                "archetype_idx": j,
                "sorted_candidates": sort_idx,
                "sorted_labels": sorted_labels,
                "sorted_weights": sorted_weights,
                "cumulative_frac": cumfrac,
                "n_effective": n_eff,
                "cross_mean": cross_mean,
                "cross_std": cross_std,
                "cross_sigma": cross_sigma,
                "cross_signal": cross_signal,
            }
        )

    summary = np.array(
        [
            r["n_effective"] if not r.get("degenerate", False) else 0
            for r in archetype_results
        ]
    )

    if plot:
        _plot_noise_floor_diagnostics(
            archetype_results, L, p, candidate_labels,
            uniform_expectation, cumulative_threshold,
            cross_archetype_sigma,
        )

    return {
        "M_normed": M_normed,
        "archetypes": archetype_results,
        "summary": summary,
    }


def _plot_noise_floor_diagnostics(
    archetype_results: List[Dict],
    L: int,
    p: int,
    candidate_labels: List[str],
    uniform_expectation: float,
    cumulative_threshold: float,
    cross_archetype_sigma: float,
):
    """
    Internal helper: one figure per archetype with two subplots.

    Left  — sorted loading bar chart with cumulative curve and threshold.
    Right — cross-archetype comparison (loading vs. mean ± sigma band).
    """
    for res in archetype_results:
        if res.get("degenerate", False):
            continue

        j = res["archetype_idx"]
        n_eff = res["n_effective"]
        sorted_w = res["sorted_weights"]
        cumfrac = res["cumulative_frac"]
        sorted_labs = res["sorted_labels"]
        sort_idx = res["sorted_candidates"]

        n_show = min(L, max(n_eff + 10, 20))

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(
            f"Archetype {j}  —  effective size = {n_eff} / {L} candidates "
            f"(at {cumulative_threshold:.0%} weight)",
            fontsize=12, fontweight="bold",
        )

        # ─── Left: sorted loadings + cumulative curve ─────────────
        ax = axes[0]
        x_pos = np.arange(n_show)
        colors = ["#2166ac" if i < n_eff else "#d1e5f0" for i in range(n_show)]
        ax.bar(x_pos, sorted_w[:n_show], color=colors, edgecolor="none")
        ax.axhline(uniform_expectation, color="red", ls="--", lw=1,
                    label=f"uniform = 1/{L}")

        ax2 = ax.twinx()
        ax2.plot(x_pos, cumfrac[:n_show], color="black", lw=1.5, marker=".",
                 markersize=4, label="cumulative")
        ax2.axhline(cumulative_threshold, color="grey", ls=":", lw=1)
        ax2.set_ylabel("cumulative fraction")
        ax2.set_ylim(0, 1.05)

        ax.set_xticks(x_pos)
        ax.set_xticklabels(
            [_truncate(s, 12) for s in sorted_labs[:n_show]],
            rotation=70, ha="right", fontsize=7,
        )
        ax.set_ylabel("normalised loading")
        ax.set_title("Sorted candidate loadings")
        ax.legend(loc="upper right", fontsize=8)

        # ─── Right: cross-archetype comparison ────────────────────
        ax = axes[1]

        # Reorder cross-archetype stats to match the sorted order
        cross_mean_sorted = res["cross_mean"][sort_idx]
        cross_std_sorted = res["cross_std"][sort_idx]
        cross_sig_sorted = res["cross_signal"][sort_idx]

        x_pos2 = np.arange(n_show)

        # Bars: actual loading, coloured by signal status
        ax.bar(x_pos2, sorted_w[:n_show], color=[
            "#2166ac" if s else "#d1e5f0" for s in cross_sig_sorted[:n_show]
        ], edgecolor="none", label="loading in this archetype")

        # Cross-archetype mean as points
        ax.scatter(x_pos2, cross_mean_sorted[:n_show],
                   color="#333333", marker="_", s=80, zorder=3,
                   label="mean in other archetypes")

        # Threshold band: mean + sigma * SD
        if p >= 3:
            threshold_line = (
                cross_mean_sorted[:n_show]
                + cross_archetype_sigma * cross_std_sorted[:n_show]
            )
            ax.plot(x_pos2, threshold_line,
                    color="#d95f02", ls="--", lw=1.2,
                    label=f"mean + {cross_archetype_sigma:.0f}σ threshold")

        ax.axhline(uniform_expectation, color="red", ls=":", lw=0.8,
                    label=f"uniform = 1/{L}")

        ax.set_xticks(x_pos2)
        ax.set_xticklabels(
            [_truncate(s, 12) for s in sorted_labs[:n_show]],
            rotation=70, ha="right", fontsize=7,
        )
        ax.set_ylabel("normalised loading")
        ax.set_title("Cross-archetype signal detection")
        ax.legend(loc="upper right", fontsize=7)

        fig.tight_layout(rect=[0, 0, 1, 0.93])
        plt.show()


# ---------------------------------------------------------------------------
# Abundance-weighted signal relevance
# ---------------------------------------------------------------------------


def abundance_weighted_signal(
    noise_floor_results: Dict[str, object],
    S: np.ndarray,
    candidate_labels: Optional[List[str]] = None,
    plot: bool = True,
) -> Dict[str, object]:
    """
    Weight per-archetype signal candidates by how prevalent each archetype
    is across precincts (abundance), producing a single relevance score
    per candidate that accounts for both archetype-specificity and
    archetype prevalence.

    This function takes the output of ``endmember_noise_floor`` and an
    abundance matrix, and answers: "Given that candidate i is signal in
    archetype j, how much does that actually matter for the election?"

    Parameters
    ----------
    noise_floor_results : dict
        Output of ``endmember_noise_floor``.
    S : ndarray, shape (p, N)
        Abundance (fraction) matrix from SUNSAL / FCLS.
        p = number of archetypes, N = number of precincts.
        Each column should sum to ~1 (fully constrained) but this is
        not enforced.
    candidate_labels : list of str, optional
        Human-readable candidate names.  If None, uses labels from
        ``noise_floor_results`` or integer indices.
    plot : bool, optional
        If True, produce summary plots (default True).

    Returns
    -------
    results : dict with keys

        ``"archetype_prevalence"`` : ndarray (p,), mean abundance of each
                                     archetype across all precincts.

        ``"archetype_total_abundance"`` : ndarray (p,), sum of abundance
                                          of each archetype across all
                                          precincts.

        ``"candidate_relevance"`` : ndarray (L,), per-candidate relevance
            score.  For each archetype where the candidate is signal,
            their normalised loading is multiplied by that archetype's
            mean abundance; these are summed across archetypes.
            High score = strong signal in prevalent archetypes.

        ``"candidate_max_archetype"`` : ndarray (L,) of int, the archetype
            index where each candidate has the highest relevance
            contribution (i.e. their "home" archetype).

        ``"candidate_signal_in"`` : list of lists, for each candidate
            which archetype indices they are signal in.

        ``"per_archetype"`` : list of dicts (one per archetype), each with:

            ``"archetype_idx"``       — int.

            ``"mean_abundance"``      — float, archetype prevalence.

            ``"signal_candidates"``   — list of str, labels of signal
                                        candidates in this archetype.

            ``"signal_loadings"``     — ndarray, their normalised loadings.

            ``"signal_relevance"``    — ndarray, loading × prevalence for
                                        each signal candidate.
    """
    S = np.asarray(S, dtype=float)
    if S.ndim != 2:
        raise ValueError(f"S must be 2-D, got shape {S.shape}")

    arch_list = noise_floor_results["archetypes"]
    M_normed = noise_floor_results["M_normed"]
    L, p = M_normed.shape
    p_s, N = S.shape

    if p_s != p:
        raise ValueError(
            f"Abundance matrix has {p_s} archetypes but endmember matrix "
            f"has {p}.  These must match."
        )

    # Resolve labels
    if candidate_labels is None:
        first_arch = arch_list[0]
        if "sorted_labels" in first_arch and not first_arch.get("degenerate"):
            # Reconstruct original-order labels from sorted data
            all_labels = [""] * L
            for idx, lab in zip(
                first_arch["sorted_candidates"], first_arch["sorted_labels"]
            ):
                all_labels[idx] = lab
            candidate_labels = all_labels
        else:
            candidate_labels = [str(i) for i in range(L)]

    # ── Archetype prevalence ──────────────────────────────────────────
    archetype_prevalence = S.mean(axis=1)      # (p,)
    archetype_total = S.sum(axis=1)            # (p,)

    # ── Per-candidate relevance ───────────────────────────────────────
    candidate_relevance = np.zeros(L)
    candidate_max_contribution = np.full(L, -1.0)
    candidate_max_archetype = np.zeros(L, dtype=int)
    candidate_signal_in: List[List[int]] = [[] for _ in range(L)]

    per_archetype_results = []

    for res in arch_list:
        if res.get("degenerate", False):
            per_archetype_results.append({
                "archetype_idx": res["archetype_idx"],
                "degenerate": True,
            })
            continue

        j = res["archetype_idx"]
        prevalence_j = archetype_prevalence[j]
        signal_mask = res["cross_signal"]                # (L,) bool
        loadings = M_normed[:, j]                        # (L,)

        signal_indices = np.where(signal_mask)[0]
        signal_labels = [candidate_labels[i] for i in signal_indices]
        signal_loadings = loadings[signal_indices]
        signal_relevance = signal_loadings * prevalence_j

        for i in signal_indices:
            contrib = loadings[i] * prevalence_j
            candidate_relevance[i] += contrib
            candidate_signal_in[i].append(j)

            if contrib > candidate_max_contribution[i]:
                candidate_max_contribution[i] = contrib
                candidate_max_archetype[i] = j

        # Sort signal candidates by relevance within this archetype
        rel_order = np.argsort(signal_relevance)[::-1]

        per_archetype_results.append({
            "archetype_idx": j,
            "mean_abundance": prevalence_j,
            "signal_candidates": [signal_labels[k] for k in rel_order],
            "signal_loadings": signal_loadings[rel_order],
            "signal_relevance": signal_relevance[rel_order],
        })

    if plot:
        _plot_abundance_weighted(
            per_archetype_results, candidate_relevance, candidate_labels,
            candidate_max_archetype, archetype_prevalence, L, p,
        )

    return {
        "archetype_prevalence": archetype_prevalence,
        "archetype_total_abundance": archetype_total,
        "candidate_relevance": candidate_relevance,
        "candidate_max_archetype": candidate_max_archetype,
        "candidate_signal_in": candidate_signal_in,
        "per_archetype": per_archetype_results,
    }


def _plot_abundance_weighted(
    per_archetype_results: List[Dict],
    candidate_relevance: np.ndarray,
    candidate_labels: List[str],
    candidate_max_archetype: np.ndarray,
    archetype_prevalence: np.ndarray,
    L: int,
    p: int,
):
    """
    Internal helper: two summary plots.

    Left  — archetype prevalence (mean abundance) as horizontal bars.
    Right — top candidates ranked by abundance-weighted relevance score,
            coloured by their primary archetype.
    """
    # Colour palette for archetypes (up to 10)
    # arch_colors = [
    #     "#2166ac", "#b2182b", "#1b7837", "#d95f02",
    #     "#7570b3", "#e7298a", "#66a61e", "#e6ab02",
    #     "#a6761d", "#666666",
    # ]
    arch_colors = [f"C{j}" for j in range(10)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Abundance-weighted candidate relevance",
        fontsize=12, fontweight="bold",
    )

    # ─── Left: archetype prevalence ───────────────────────────────
    ax = axes[0]
    arch_indices = np.arange(p)
    bar_colors = [arch_colors[j % len(arch_colors)] for j in arch_indices]
    ax.barh(arch_indices, archetype_prevalence, color=bar_colors,
            edgecolor="none", height=0.6)
    ax.set_yticks(arch_indices)
    ax.set_yticklabels([f"Archetype {j}" for j in arch_indices], fontsize=9)
    ax.set_xlabel("mean abundance across precincts")
    ax.set_title("Archetype prevalence")
    ax.invert_yaxis()

    # Annotate with percentage
    for j in arch_indices:
        ax.text(archetype_prevalence[j] + 0.005, j,
                f"{archetype_prevalence[j]:.1%}",
                va="center", fontsize=8)

    # ─── Right: top candidates by relevance ───────────────────────
    ax = axes[1]

    # Show top candidates (nonzero relevance, capped for readability)
    nonzero = candidate_relevance > 1e-10
    if nonzero.sum() == 0:
        ax.text(0.5, 0.5, "No signal candidates detected",
                ha="center", va="center", transform=ax.transAxes)
    else:
        rel_order = np.argsort(candidate_relevance)[::-1]
        n_show = min(int(nonzero.sum()), 30)
        top_idx = rel_order[:n_show]

        y_pos = np.arange(n_show)
        bar_c = [
            arch_colors[candidate_max_archetype[i] % len(arch_colors)]
            for i in top_idx
        ]
        ax.barh(y_pos, candidate_relevance[top_idx], color=bar_c,
                edgecolor="none", height=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(
            [_truncate(candidate_labels[i], 18) for i in top_idx],
            fontsize=8,
        )
        ax.set_xlabel("relevance (loading × prevalence, summed)")
        ax.set_title("Top candidates by weighted relevance")
        ax.invert_yaxis()

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    plt.show()


def _truncate(s: str, maxlen: int) -> str:
    """Truncate a label string for plot readability."""
    return s if len(s) <= maxlen else s[: maxlen - 1] + "…"