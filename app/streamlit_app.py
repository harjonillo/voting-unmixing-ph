"""Voting-archetype explorer.

Reads the artifacts written by scripts/run_pipeline.py (data/processed/) and
the shapefiles in data/shapefiles/, and shows archetype abundances and
endmember loadings at a chosen aggregation level.

Run from the repo root:
    streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import LEVEL_COLS, aggregate_abundances, dominant_archetype
from src.config import load_config
from src.data.loading import load_processed, load_sweep
from src.figures.maps import plotly_choropleth
from src.geo import (
    canonical_province,
    join_municipalities,
    join_provinces,
    join_regions,
    load_municipalities,
    load_provinces,
)
from src.unmixing.matching import archetype_lineage

st.set_page_config(page_title="PH voting archetypes", layout="wide")

LEVEL_LABELS = {
    "national": "National",
    "region": "Region",
    "province": "Province",
    "municipality": "City / municipality",
    "clustered_precinct": "Clustered precinct",
}
MAPPABLE = {"region", "province", "municipality"}


# ---------------------------------------------------------------------------
# Cached loading
# ---------------------------------------------------------------------------

@st.cache_data
def get_processed():
    config = load_config()
    endmembers, abundances, meta = load_processed(config)
    return endmembers, abundances, meta


@st.cache_resource
def get_provinces():
    return load_provinces(load_config())


@st.cache_resource
def get_municipalities():
    return load_municipalities(load_config())


@st.cache_data
def get_aggregate(level: str, weighted: bool):
    _, abundances, _ = get_processed()
    return aggregate_abundances(
        abundances,
        level=level,
        weight_col="information.numberOfValidBallot" if weighted else None,
    )


@st.cache_data
def get_sweep():
    return load_sweep(load_config())


@st.cache_data
def sweep_province_stats(p: int):
    """Province-level mean/std across trials for sweep entry p.

    Municipality aggregates are re-aggregated per trial (ballot-weighted,
    exact) to province level, then mean/std are taken across trials.
    """
    entry = get_sweep()[p]
    df = entry["agg_trials"].copy()
    arch_cols_p = [c for c in df.columns if c.startswith("arch_")]
    wcol = "information.numberOfValidBallot"
    df["PROV_KEY"] = [
        canonical_province(pr, rg) for pr, rg in zip(df["PROVINCE"], df["REGION"])
    ]
    for c in arch_cols_p:
        df[c + "_w"] = df[c] * df[wcol]
    g = df.groupby(["trial", "PROV_KEY"], observed=True).sum(numeric_only=True)
    per_trial = pd.DataFrame(
        {c: g[c + "_w"] / g[wcol] for c in arch_cols_p}
    ).reset_index()
    mean = per_trial.groupby("PROV_KEY")[arch_cols_p].mean()
    std = per_trial.groupby("PROV_KEY")[arch_cols_p].std(ddof=1)
    return mean, std


try:
    endmembers, abundances, meta = get_processed()
except FileNotFoundError:
    st.error(
        "Processed artifacts not found. Run `python scripts/run_pipeline.py` "
        "from the repo root first (see README)."
    )
    st.stop()

arch_cols = list(endmembers.columns)
n_arch = len(arch_cols)
candidate_labels = list(endmembers.index)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("PH voting archetypes")
st.sidebar.caption(
    f"2025 senatorial race — {meta['n_archetypes']} archetypes, "
    f"{len(abundances):,} clustered precincts "
    f"(HySime kf = {meta['hysime_kf']}, RMSE = {meta['rmse']:.4f})"
)

level = st.sidebar.radio(
    "Aggregation level",
    list(LEVEL_LABELS),
    format_func=LEVEL_LABELS.get,
    index=1,
)

value_kind = st.sidebar.selectbox(
    "Quantity",
    ["Archetype abundance", "Dominant archetype", "Turnout"],
)

sel_arch = st.sidebar.selectbox(
    "Archetype", arch_cols,
    format_func=lambda c: f"Archetype {c.split('_')[1]}",
    help="Colors the map when Quantity = Archetype abundance, and picks "
         "which archetype's loadings appear beside the map.",
)

weighted = st.sidebar.checkbox(
    "Weight means by valid ballots", value=True,
    help="Off = plain mean over precincts",
)

regions_all = sorted(abundances["REGION"].unique())
region_filter = st.sidebar.multiselect(
    "Filter regions (empty = all)", regions_all, default=[],
)

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

df_ab = abundances
if region_filter:
    df_ab = df_ab[df_ab["REGION"].isin(region_filter)]

agg = aggregate_abundances(
    df_ab,
    level=level if level != "national" else "national",
    weight_col="information.numberOfValidBallot" if weighted else None,
)
agg["dominant"] = dominant_archetype(agg, arch_cols) if len(agg) else []
if "information.numberOfActuallyVoters" in agg.columns and "information.numberOfRegisteredVoters" in agg.columns:
    agg["turnout_pct"] = 100 * agg["information.numberOfActuallyVoters"] / agg["information.numberOfRegisteredVoters"]

if value_kind == "Archetype abundance":
    value_col, colorbar = sel_arch, f"mean abundance ({sel_arch})"
elif value_kind == "Dominant archetype":
    value_col, colorbar = "dominant", "dominant archetype"
else:
    value_col, colorbar = "turnout_pct", "turnout (%)"

name_col = LEVEL_COLS[level][-1] if LEVEL_COLS[level] else None


def loadings_fig(arch_col: str, top_n: int = 15, height: int | None = None):
    """Horizontal bar chart of the top-N candidate loadings for one archetype."""
    sub = endmembers[arch_col].sort_values(ascending=False).head(top_n)
    fig = px.bar(
        x=sub.values[::-1], y=sub.index[::-1], orientation="h",
        labels={"x": "loading", "y": ""},
        title=f"Archetype {arch_col.split('_')[1]} — top {top_n} loadings",
    )
    fig.update_layout(
        height=height or max(300, 24 * top_n),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_map, tab_loadings, tab_dist, tab_table, tab_compare = st.tabs(
    ["Map / overview", "Endmember loadings", "Abundance distributions", "Table",
     "Model comparison"]
)

with tab_map:
    if level == "national":
        st.subheader("National overview")
        cols = st.columns(n_arch)
        row = agg.iloc[0]
        for c, col in zip(arch_cols, cols):
            col.metric(f"Archetype {c.split('_')[1]}", f"{row[c]:.1%}")
        st.caption("Mean archetype abundance across all precincts"
                   + (" (ballot-weighted)" if weighted else ""))
        col_left, col_right = st.columns([1, 1])
        fig = px.bar(
            x=[f"Archetype {c.split('_')[1]}" for c in arch_cols],
            y=[row[c] for c in arch_cols],
            labels={"x": "", "y": "mean abundance"},
        )
        col_left.plotly_chart(fig, use_container_width=True)
        col_right.plotly_chart(loadings_fig(sel_arch, height=450),
                               use_container_width=True)

    elif level == "clustered_precinct":
        st.info(
            "Clustered precincts have no boundary geometry — see the "
            "distribution and table tabs; the map is available down to the "
            "municipality level."
        )
        st.dataframe(agg.head(1000), use_container_width=True)

    else:
        provinces = get_provinces()
        agg_prov = aggregate_abundances(
            df_ab, level="province",
            weight_col="information.numberOfValidBallot" if weighted else None,
        )
        if value_kind == "Turnout":
            for a in (agg_prov,):
                a["turnout_pct"] = 100 * a["information.numberOfActuallyVoters"] / a["information.numberOfRegisteredVoters"]

        if level == "region":
            gdf, unmatched = join_regions(agg_prov, provinces, agg)
            hover = "REGION"
        elif level == "province":
            gdf, unmatched = join_provinces(agg, provinces)
            hover = "PROV_KEY"
        else:  # municipality
            municipalities = get_municipalities()
            if municipalities is None:
                st.warning(
                    "Municipal boundaries not found "
                    "(`data/shapefiles/municipalities.geojson`). Run "
                    "`python scripts/fetch_boundaries.py`, or use the other "
                    "tabs for municipality-level plots."
                )
                gdf, unmatched = None, []
            else:
                gdf, rate, unmatched_df = join_municipalities(agg, municipalities)
                unmatched = unmatched_df["CITY_MUNICIPALITY"].tolist()
                st.caption(f"Matched {rate:.1%} of municipalities to boundaries.")
                hover = "CITY_MUNICIPALITY"

        if gdf is not None and len(gdf):
            # BSthesis shapefiles are high-resolution; simplify for display
            tol = 0.001 if level == "municipality" else 0.005
            if value_col == "dominant":
                # recompute after the geometry join (units may have merged)
                dom = dominant_archetype(gdf, arch_cols)
                has_data = gdf[arch_cols[0]].notna().to_numpy()
                gdf["dominant"] = [str(d) if ok else None for d, ok in zip(dom, has_data)]
                fig = plotly_choropleth(gdf, "dominant", hover_name=hover,
                                        simplify_tolerance=tol)
            else:
                fig = plotly_choropleth(
                    gdf, value_col, hover_name=hover, simplify_tolerance=tol,
                )
            fig.update_coloraxes(colorbar_title=colorbar)
            col_map, col_load = st.columns([5, 3])
            col_map.plotly_chart(fig, use_container_width=True)
            col_load.plotly_chart(loadings_fig(sel_arch, height=650),
                                  use_container_width=True)
            if value_kind != "Archetype abundance":
                col_load.caption(
                    "Loadings of the archetype selected in the sidebar "
                    "(the map itself shows "
                    f"{'the dominant archetype' if value_kind == 'Dominant archetype' else 'turnout'})."
                )

        if unmatched:
            with st.expander(f"{len(unmatched)} units without a matched boundary"):
                st.write(sorted(map(str, unmatched)))

with tab_loadings:
    st.subheader("Endmember (archetype) loadings")
    st.caption("Candidate weights per archetype from MVSA — a national-level "
               "property of the unmixing, independent of the aggregation level.")
    top_n = st.slider("Top N candidates", 5, len(candidate_labels), 15)
    which = st.multiselect(
        "Archetypes", arch_cols, default=arch_cols,
        format_func=lambda c: f"Archetype {c.split('_')[1]}",
    )
    ncols = min(3, max(1, len(which)))
    cols = st.columns(ncols)
    for i, c in enumerate(which):
        sub = endmembers[c].sort_values(ascending=False).head(top_n)
        fig = px.bar(
            x=sub.values[::-1], y=sub.index[::-1], orientation="h",
            labels={"x": "loading", "y": ""},
            title=f"Archetype {c.split('_')[1]}",
        )
        fig.update_layout(height=max(300, 24 * top_n), margin=dict(l=0, r=0, t=40, b=0))
        cols[i % ncols].plotly_chart(fig, use_container_width=True)

with tab_dist:
    st.subheader(f"Abundance distributions — {LEVEL_LABELS[level]} level")
    if level == "national":
        source, unit = df_ab, "precinct"
    else:
        source, unit = agg, LEVEL_LABELS[level].lower()
    ncols = min(4, n_arch)
    cols = st.columns(ncols)
    for j, c in enumerate(arch_cols):
        fig = px.histogram(
            source, x=c, nbins=40,
            labels={c: "abundance"},
            title=f"Archetype {c.split('_')[1]}",
        )
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=40, b=0),
                          yaxis_title=f"# {unit}s")
        cols[j % ncols].plotly_chart(fig, use_container_width=True)

with tab_table:
    st.subheader(f"Aggregated values — {LEVEL_LABELS[level]} level")
    st.dataframe(agg, use_container_width=True, height=600)
    st.download_button(
        "Download CSV",
        agg.to_csv(index=False).encode(),
        file_name=f"abundances_{level}.csv",
        mime="text/csv",
    )

with tab_compare:
    sweep = get_sweep()
    if not sweep:
        st.info("No sweep artifacts found — run `python scripts/run_sweep.py` "
                "from the repo root (precomputes p = p_min..p_max × n_trials).")
        st.stop()

    ps = sorted(sweep)
    n_trials = sweep[ps[0]]["meta"]["n_trials"]
    st.subheader("Endmember-count comparison")
    st.caption(f"{n_trials} MVSA+SUNSAL trials per p, archetypes Hungarian-aligned "
               "(cosine) to each p's lowest-RMSE trial. All values precomputed by "
               "`scripts/run_sweep.py`.")

    # ── RMSE and stability vs p ─────────────────────────────────────────
    col_rmse, col_stab = st.columns(2)
    rmse_mean = [sweep[p]["meta"]["rmse_mean"] for p in ps]
    rmse_std = [sweep[p]["meta"]["rmse_std"] for p in ps]
    fig = px.scatter(x=ps, y=rmse_mean, error_y=rmse_std,
                     labels={"x": "number of archetypes p", "y": "reconstruction RMSE"},
                     title="RMSE vs p (mean ± std over trials)")
    fig.update_traces(mode="lines+markers")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=40, b=0))
    col_rmse.plotly_chart(fig, use_container_width=True)

    stab_rows = [
        {"p": p, "archetype": k, "stability": s}
        for p in ps
        for k, s in enumerate(sweep[p]["meta"]["stability_per_archetype"])
    ]
    stab_df = pd.DataFrame(stab_rows)
    fig = px.strip(stab_df, x="p", y="stability",
                   title="Trial-to-reference cosine similarity per archetype")
    mean_line = stab_df.groupby("p")["stability"].mean().reset_index()
    fig.add_scatter(x=mean_line["p"], y=mean_line["stability"],
                    mode="lines+markers", name="mean", line=dict(color="crimson"))
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=40, b=0),
                      xaxis_title="number of archetypes p")
    col_stab.plotly_chart(fig, use_container_width=True)

    # ── Archetype lineage (which archetype splits as p grows) ───────────
    st.markdown("#### Archetype lineage")
    st.caption("Consecutive p Hungarian-matched by cosine similarity; the red link "
               "marks the archetype that appears/splits when p increases by one. "
               "Nodes are labelled with each archetype's top-loading candidate.")
    loadings_by_p = {p: sweep[p]["loadings_mean"].to_numpy() for p in ps}
    edges = archetype_lineage(loadings_by_p)

    node_ids, node_labels, node_x, node_y = {}, [], [], []
    for pi, p in enumerate(ps):
        lm = sweep[p]["loadings_mean"]
        for k in range(p):
            node_ids[(p, k)] = len(node_labels)
            top = lm.iloc[:, k].idxmax().split(" [")[0].split(",")[0].title()
            node_labels.append(f"p{p}·A{k} {top}")
            node_x.append(pi / max(len(ps) - 1, 1))
            node_y.append((k + 0.5) / p)

    fig = go.Figure(go.Sankey(
        arrangement="fixed",
        node=dict(label=node_labels, x=node_x, y=node_y, pad=8, thickness=12),
        link=dict(
            source=[node_ids[(e["p_from"], e["k_from"])] for e in edges],
            target=[node_ids[(e["p_to"], e["k_to"])] for e in edges],
            value=[max(e["similarity"], 0.05) for e in edges],
            color=["rgba(214,39,40,0.55)" if e["split"] else "rgba(100,120,160,0.35)"
                   for e in edges],
            customdata=[round(e["similarity"], 3) for e in edges],
            hovertemplate="similarity %{customdata}<extra></extra>",
        ),
    ))
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ── Per-p detail: loadings with error bars + province map ───────────
    st.markdown("#### Detail at a chosen p")
    sel_p = st.selectbox("Number of archetypes", ps,
                         index=len(ps) - 1, key="compare_p")
    entry = sweep[sel_p]
    lm, ls = entry["loadings_mean"], entry["loadings_std"]
    arch_cols_p = list(lm.columns)

    map_col, load_col = st.columns([1, 1])
    with map_col:
        sel_arch_p = st.selectbox(
            "Archetype", arch_cols_p,
            format_func=lambda c: f"Archetype {c.split('_')[1]}", key="compare_arch",
        )
        show_std = st.radio("Map shows", ["Mean abundance", "Std across trials"],
                            horizontal=True, key="compare_stat") == "Std across trials"
        mean_prov, std_prov = sweep_province_stats(sel_p)
        stats = (std_prov if show_std else mean_prov)[[sel_arch_p]].reset_index()
        gdf = get_provinces().merge(stats, on="PROV_KEY", how="left")
        fig = plotly_choropleth(gdf, sel_arch_p, hover_name="PROV_KEY",
                                simplify_tolerance=0.005)
        fig.update_coloraxes(colorbar_title=("std" if show_std else "mean")
                             + f" ({sel_arch_p})")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)
    with load_col:
        top_n_p = st.slider("Top N candidates", 5, len(lm), 15, key="compare_topn")
        sub = lm[sel_arch_p].sort_values(ascending=False).head(top_n_p)
        err = ls.loc[sub.index, sel_arch_p]
        fig = px.bar(
            x=sub.values[::-1], y=sub.index[::-1], orientation="h",
            error_x=err.values[::-1],
            labels={"x": "loading (mean ± std over trials)", "y": ""},
            title=f"Archetype {sel_arch_p.split('_')[1]} — top {top_n_p} loadings",
        )
        fig.update_layout(height=max(400, 26 * top_n_p),
                          margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
