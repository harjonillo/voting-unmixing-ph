"""
archetype_plots.py — bar-chart helpers for archetype loadings and per-archetype
abundance summaries. Originally inlined in the trial-clustering and analysis
notebooks; consolidated here so all notebooks share the same plotting code.
"""

import numpy as np
import matplotlib.pyplot as plt


def plot_archetype_loadings(
    loadings_list,
    candidate_labels,
    ax=None,
    stds_list=None,
    series_labels=None,
    series_colors=None,
    top_n=15,
    title=None,
    xlabel='Loading',
):
    """Grouped horizontal bar chart of top-N candidate loadings for one or more archetypes.

    Single archetype with error bars: pass a 1-element list and an `stds_list`.
    Compare two archetypes:           pass a 2-element list and `series_labels`.

    Ordering: union of each series's top-N, sorted by max loading across series.
    If `ax` is None a new figure is created, sized to the union length.
    """
    loadings_list = [np.asarray(s) for s in loadings_list]
    n_series = len(loadings_list)

    top_sets = [set(np.argsort(s)[::-1][:top_n]) for s in loadings_list]
    union = set().union(*top_sets)
    order = np.asarray(
        sorted(union, key=lambda k: -max(s[k] for s in loadings_list))
    )

    if ax is None:
        fig, ax = plt.subplots(figsize=(7, max(4.0, 0.32 * len(order))))

    y = np.arange(len(order))
    bar_h = 0.8 / n_series
    offsets = (np.arange(n_series) - (n_series - 1) / 2) * bar_h

    for s_idx, s in enumerate(loadings_list):
        color = series_colors[s_idx] if series_colors else f'C{s_idx}'
        label = series_labels[s_idx] if series_labels else None
        xerr  = stds_list[s_idx][order] if stds_list is not None else None
        ax.barh(
            y + offsets[s_idx],
            s[order],
            height=bar_h,
            color=color,
            edgecolor='white',
            label=label,
            xerr=xerr,
            error_kw=dict(ecolor='black', lw=0.8, capsize=2),
        )

    ax.set_yticks(y)
    ax.set_yticklabels([candidate_labels[k] for k in order], fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color='black', lw=0.6)
    ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, fontsize=10)
    if series_labels:
        ax.legend()
    return ax


def plot_archetypes_loadings_grid(
    loadings,
    candidate_labels,
    stds=None,
    subtitles=None,
    top_n=15,
    suptitle='',
    xlabel='Loading',
    colors=None,
):
    """Grid of horizontal top-N candidate bar charts, one panel per archetype column.

    loadings:  (L, K) mean loadings (consensus = single vector per archetype,
               multi-trial = per-archetype mean across trials).
    stds:      (L, K) error-bar magnitudes or None (no error bars).
    subtitles: length-K list of per-panel titles; default f'Archetype k'.
    """
    loadings = np.asarray(loadings)
    L, K = loadings.shape
    ncols = min(K, 4)
    nrows = int(np.ceil(K / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, max(4.5, 0.32 * top_n) * nrows))
    axes_flat = np.atleast_1d(axes).flatten()
    for k in range(K):
        color = colors[k] if colors is not None else f'C{k % 10}'
        sub   = subtitles[k] if subtitles is not None else f'Archetype {k}'
        plot_archetype_loadings(
            [loadings[:, k]],
            candidate_labels,
            ax=axes_flat[k],
            stds_list=[stds[:, k]] if stds is not None else None,
            series_colors=[color],
            top_n=top_n,
            title=sub,
            xlabel=xlabel,
        )
    for k in range(K, len(axes_flat)):
        axes_flat[k].set_visible(False)
    if suptitle:
        fig.suptitle(suptitle, y=1.02)
    fig.tight_layout()
    plt.show()


def build_abundance_panel(name, A, labels=None):
    """Build a panel dict for plot_total_abundance_bars.

    If `labels` is None: `A` is (K, N); one consensus vector per archetype. Totals are
    A.sum(axis=1), sems are zero, sizes are one, n_noise is zero.

    If `labels` is given: `A` is (M, N) per-vector abundances and `labels` (M,) assigns
    each row to a cluster (noise = -1 is excluded). Per-cluster total is the mean of
    member row sums; sem is SEM across members.
    """
    if labels is None:
        totals = A.sum(axis=1)
        K = A.shape[0]
        return {
            'name': name,
            'clusters': list(range(K)),
            'totals':   totals,
            'sems':     np.zeros(K),
            'sizes':    np.ones(K, dtype=int),
            'n_noise':  0,
        }
    totals_per_vec = A.sum(axis=1)
    clusters = sorted(c for c in np.unique(labels) if c >= 0)
    n_noise  = int((labels == -1).sum())
    totals   = np.zeros(len(clusters))
    sems     = np.zeros(len(clusters))
    sizes    = np.zeros(len(clusters), dtype=int)
    for j, c in enumerate(clusters):
        m = labels == c
        sizes[j]  = int(m.sum())
        vals      = totals_per_vec[m]
        totals[j] = vals.mean()
        sems[j]   = vals.std(ddof=1) / np.sqrt(sizes[j]) if sizes[j] > 1 else 0.0
    return {
        'name': name, 'clusters': clusters, 'totals': totals,
        'sems': sems, 'sizes': sizes, 'n_noise': n_noise,
    }


def plot_total_abundance_bars(
    panels,
    suptitle='',
    ylabel='Mean total abundance across precincts',
    xlabel='cluster (reordered)',
    xlabel_prefix='c',
    show_sizes=True,
    show_sems=True,
    color='steelblue',
):
    """Bar chart of per-cluster total abundance, one panel per entry in `panels`.

    Each panel dict is the output of `build_abundance_panel` (keys: name, clusters,
    totals, sems, sizes, n_noise). Within each panel, clusters are re-ordered by
    decreasing total abundance.
    """
    n_panels = len(panels)
    fig, axes = plt.subplots(1, n_panels, figsize=(3.8 * n_panels, 3.6),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, p in zip(axes, panels):
        totals   = np.asarray(p['totals'])
        sems     = np.asarray(p['sems']) if show_sems and p.get('sems') is not None else None
        clusters = p['clusters']
        sizes    = p['sizes']
        order = np.argsort(totals)[::-1]
        x     = np.arange(len(clusters))
        ax.bar(x, totals[order],
               yerr=(sems[order] if sems is not None else None),
               color=color, edgecolor='black', capsize=3)
        ax.set_xticks(x)
        if show_sizes:
            ax.set_xticklabels([f'{xlabel_prefix}{clusters[o]}\n(n={sizes[o]})' for o in order])
        else:
            ax.set_xticklabels([f'{xlabel_prefix}{clusters[o]}' for o in order])
        title = p['name']
        if p.get('n_noise', 0) > 0:
            title = f"{title}  (noise={p['n_noise']})"
        ax.set_title(title)
        ax.set_xlabel(xlabel)
    axes[0].set_ylabel(ylabel)
    if suptitle:
        fig.suptitle(suptitle)
    fig.tight_layout()
    plt.show()
