"""Choropleth for the current view: joins the aggregate to boundaries and
builds the figure. Used by the overview tab.
"""

import geopandas as gpd
import streamlit as st

from app.components.data import View, get_municipalities, get_provinces
from src.aggregation import aggregate_abundances, dominant_archetype
from src.figures.maps import plotly_choropleth
from src.geo import join_municipalities, join_provinces, join_regions

# BSthesis shapefiles are high-resolution; simplify for display
SIMPLIFY_TOLERANCE = {"municipality": 0.001}
DEFAULT_TOLERANCE = 0.005


def join_to_boundaries(view: View):
    """Merge `view.agg` onto the boundaries for its level.

    Returns (gdf, hover_col, unmatched_names); gdf is None when the municipal
    boundaries are missing.
    """
    level = view.controls.level
    provinces = get_provinces()

    if level == "region":
        # Province polygons dissolved by the data's own province->region map.
        agg_prov = aggregate_abundances(
            view.df_ab, level="province", weight_col=view.controls.weight_col,
        )
        gdf, unmatched = join_regions(agg_prov, provinces, view.agg)
        return gdf, "REGION", unmatched

    if level == "province":
        gdf, unmatched = join_provinces(view.agg, provinces)
        return gdf, "PROV_KEY", unmatched

    municipalities = get_municipalities()
    if municipalities is None:
        st.warning(
            "Municipal boundaries not found "
            "(`data/shapefiles/municipalities.geojson`). Run "
            "`python scripts/fetch_boundaries.py`, or use the other "
            "tabs for municipality-level plots."
        )
        return None, None, []

    gdf, rate, unmatched_df = join_municipalities(view.agg, municipalities)
    st.caption(f"Matched {rate:.1%} of municipalities to boundaries.")
    return gdf, "CITY_MUNICIPALITY", unmatched_df["CITY_MUNICIPALITY"].tolist()


def choropleth_fig(gdf: gpd.GeoDataFrame, view: View, hover: str):
    """Color `gdf` by the quantity the sidebar selected."""
    tol = SIMPLIFY_TOLERANCE.get(view.controls.level, DEFAULT_TOLERANCE)

    if view.value_col == "dominant":
        # recompute after the geometry join (units may have merged)
        dom = dominant_archetype(gdf, view.arch_cols)
        has_data = gdf[view.arch_cols[0]].notna().to_numpy()
        gdf["dominant"] = [str(d) if ok else None for d, ok in zip(dom, has_data)]

    fig = plotly_choropleth(
        gdf, view.value_col, hover_name=hover, simplify_tolerance=tol,
    )
    fig.update_coloraxes(colorbar_title=view.colorbar)
    return fig


def render_unmatched(unmatched: list) -> None:
    if unmatched:
        with st.expander(f"{len(unmatched)} units without a matched boundary"):
            st.write(sorted(map(str, unmatched)))
