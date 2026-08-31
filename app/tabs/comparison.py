"""Model-comparison tab: how the decomposition changes with the endmember
count p. Everything shown here is precomputed by `scripts/run_sweep.py`.
"""

from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import theme
from app.components.charts import loadings_bar
from app.components.constants import LEVEL_LABELS, arch_label
from app.components.data import View, get_sweep, sweep_level_stats
from app.components.map import choropleth_fig, join_to_boundaries, render_unmatched
from src.unmixing.matching import archetype_lineage


def render(view: View) -> None:
    year = view.controls.year
    sweep = get_sweep(year)
    if not sweep:
        st.info(
            f"No sweep artifacts for {year} — run `python scripts/run_sweep.py "
            f"--config configs/config_{year}.ini` from the repo root "
            "(precomputes p = p_min..p_max × n_trials)."
        )
        return

    ps = sorted(sweep)
    n_trials = sweep[ps[0]]["meta"]["n_trials"]
    st.subheader("Endmember-count comparison")
    st.caption(
        f"{n_trials} MVSA+SUNSAL trials per p, archetypes linear sum assigned "
        "(cosine) to each p's lowest-RMSE trial. All values precomputed by "
        "`scripts/run_sweep.py`."
    )

    # _render_rmse_and_stability(sweep, ps)
    # _render_lineage(sweep, ps)
    _render_detail(view, sweep, ps)


def _render_rmse_and_stability(sweep: dict, ps: list[int]) -> None:
    col_rmse, col_stab = st.columns(2)

    rmse_mean = [sweep[p]["meta"]["rmse_mean"] for p in ps]
    rmse_std = [sweep[p]["meta"]["rmse_std"] for p in ps]
    fig = px.scatter(
        x=ps,
        y=rmse_mean,
        error_y=rmse_std,
        labels={"x": "number of archetypes p", "y": "reconstruction RMSE"},
        title="RMSE vs p (mean ± std over trials)",
    )
    fig.update_traces(mode="lines+markers")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=40, b=0))
    col_rmse.plotly_chart(fig, use_container_width=True)

    stab_df = pd.DataFrame(
        [
            {"p": p, "archetype": k, "stability": s}
            for p in ps
            for k, s in enumerate(sweep[p]["meta"]["stability_per_archetype"])
        ]
    )
    fig = px.strip(
        stab_df,
        x="p",
        y="stability",
        title="Trial-to-reference cosine similarity per archetype",
    )
    mean_line = stab_df.groupby("p")["stability"].mean().reset_index()
    fig.add_scatter(
        x=mean_line["p"],
        y=mean_line["stability"],
        mode="lines+markers",
        name="mean",
        line=dict(color=theme.HIGHLIGHT),
    )
    fig.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis_title="number of archetypes p",
    )
    col_stab.plotly_chart(fig, use_container_width=True)


def _render_lineage(sweep: dict, ps: list[int]) -> None:
    """Sankey of which archetype splits as p grows."""
    st.markdown("#### Archetype lineage")
    st.caption(
        "Consecutive p Hungarian-matched by cosine similarity; the red link "
        "marks the archetype that appears/splits when p increases by one. "
        "Nodes are labelled with each archetype's top-loading candidate."
    )

    edges = archetype_lineage({p: sweep[p]["loadings_mean"].to_numpy() for p in ps})

    node_ids, node_labels, node_x, node_y = {}, [], [], []
    for pi, p in enumerate(ps):
        lm = sweep[p]["loadings_mean"]
        for k in range(p):
            node_ids[(p, k)] = len(node_labels)
            top = lm.iloc[:, k].idxmax().split(" [")[0].split(",")[0].title()
            node_labels.append(f"p{p}·A{k} {top}")
            node_x.append(pi / max(len(ps) - 1, 1))
            node_y.append((k + 0.5) / p)

    fig = go.Figure(
        go.Sankey(
            arrangement="fixed",
            node=dict(label=node_labels, x=node_x, y=node_y, pad=8, thickness=12),
            link=dict(
                source=[node_ids[(e["p_from"], e["k_from"])] for e in edges],
                target=[node_ids[(e["p_to"], e["k_to"])] for e in edges],
                value=[max(e["similarity"], 0.05) for e in edges],
                color=[
                    (
                        theme.rgba(theme.HIGHLIGHT, 0.55)
                        if e["split"]
                        else "rgba(100,120,160,0.35)"
                    )
                    for e in edges
                ],
                customdata=[round(e["similarity"], 3) for e in edges],
                hovertemplate="similarity %{customdata}<extra></extra>",
            ),
        )
    )
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_detail(view: View, sweep: dict, ps: list[int]) -> None:
    """Loadings with error bars + a map at a chosen p.

    The map follows the sidebar aggregation level and weighting and is drawn
    with the same join/choropleth helpers as the main tab, so the two are
    consistent; only the values differ (sweep trial mean/std at the chosen p).
    """
    year = view.controls.year

    st.markdown("#### Detail at a chosen p")

    n_arch_input_col, map_arch_col, map_stat_col, n_top_cand_col = st.columns(
        [1, 1, 1, 1]
    )
    n_arch = n_arch_input_col.number_input(
        label="Number of archetypes",
        min_value=2,
        value=5,
        step=1,
        max_value=len(ps) - 1,
        key="compare_p",
    )

    entry = sweep[n_arch]
    lm, ls = entry["loadings_mean"], entry["loadings_std"]
    arch_cols_p = list(lm.columns)

    sel_arch_p = map_arch_col.selectbox(
        "Archetype",
        arch_cols_p,
        format_func=arch_label,
        key="compare_arch",
    )
    show_std = (
        map_stat_col.radio(
            "Map shows",
            ["Mean abundance", "Std across trials"],
            horizontal=True,
            key="compare_stat",
        )
        == "Std across trials"
    )
    top_n_p = n_top_cand_col.number_input(
        label="Top N candidates",
        min_value=5,
        max_value=len(lm),
        value=15,
        key="compare_topn",
    )

    level = view.controls.level
    st.caption(
        f"Map at the sidebar's **{LEVEL_LABELS[level]}** level "
        f"({'ballot-weighted' if view.controls.weighted else 'unweighted'} "
        "mean over municipalities, matching the main tab)."
    )

    mean_agg, std_agg, mean_muni = sweep_level_stats(
        year, n_arch, level, view.controls.weighted
    )
    agg = std_agg if show_std else mean_agg

    # Reuse the main tab's join + choropleth by handing them a view whose
    # frames are the sweep's trial statistics (df_ab = the trial-mean
    # municipality frame the region dissolve needs; agg = the level stats).
    map_view = replace(
        view,
        df_ab=mean_muni,
        agg=agg,
        value_col=sel_arch_p,
        colorbar=("std" if show_std else "mean") + f" ({arch_label(sel_arch_p)})",
    )

    gdf, hover, unmatched = join_to_boundaries(map_view)
    if gdf is not None and len(gdf):
        fig = choropleth_fig(gdf, map_view, hover)
        fig.update_coloraxes(colorbar_title=map_view.colorbar)
        fig.update_layout(height=620)
        st.plotly_chart(fig, use_container_width=True)
        render_unmatched(unmatched)

    # loadings
    arch_cols = st.columns([1] * n_arch)
    for c, arch_col in zip(arch_cols, arch_cols_p):
        fig = loadings_bar(
            lm,
            arch_col,
            top_n_p,
            errors=ls,
            height=max(400, 26 * top_n_p),
            x_label="loading (mean ± std over trials)",
            color=theme.archetype_color(arch_col, n_arch),
        )
        c.plotly_chart(fig, use_container_width=True)
