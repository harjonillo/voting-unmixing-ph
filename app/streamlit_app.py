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
import streamlit as st

from src.aggregation import LEVEL_COLS, aggregate_abundances, dominant_archetype
from src.config import load_config
from src.data.loading import load_processed
from src.figures.maps import plotly_choropleth
from src.geo import join_municipalities, join_provinces, join_regions, load_municipalities, load_provinces

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
    disabled=(value_kind != "Archetype abundance"),
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

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_map, tab_loadings, tab_dist, tab_table = st.tabs(
    ["Map / overview", "Endmember loadings", "Abundance distributions", "Table"]
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
        fig = px.bar(
            x=[f"Archetype {c.split('_')[1]}" for c in arch_cols],
            y=[row[c] for c in arch_cols],
            labels={"x": "", "y": "mean abundance"},
        )
        st.plotly_chart(fig, use_container_width=True)

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
            st.plotly_chart(fig, use_container_width=True)

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
