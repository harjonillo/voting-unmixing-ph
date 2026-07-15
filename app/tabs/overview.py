"""Map / overview tab."""

import plotly.express as px
import streamlit as st

from app.components.charts import loadings_bar
from app.components.constants import arch_label
from app.components.data import View
from app.components.map import choropleth_fig, join_to_boundaries, render_unmatched


def render(view: View) -> None:
    if view.controls.level == "national":
        _render_national(view)
    elif view.controls.level == "clustered_precinct":
        st.info(
            "Clustered precincts have no boundary geometry — see the "
            "distribution and table tabs; the map is available down to the "
            "municipality level."
        )
        st.dataframe(view.agg.head(1000), use_container_width=True)
    else:
        _render_map(view)


def _render_national(view: View) -> None:
    st.subheader("National overview")
    row = view.agg.iloc[0]

    cols = st.columns(view.n_arch)
    for c, col in zip(view.arch_cols, cols):
        col.metric(arch_label(c), f"{row[c]:.1%}")
    st.caption("Mean archetype abundance across all precincts"
               + (" (ballot-weighted)" if view.controls.weighted else ""))

    col_left, col_right = st.columns([1, 1])
    fig = px.bar(
        x=[arch_label(c) for c in view.arch_cols],
        y=[row[c] for c in view.arch_cols],
        labels={"x": "", "y": "mean abundance"},
    )
    col_left.plotly_chart(fig, use_container_width=True)
    col_right.plotly_chart(
        loadings_bar(view.endmembers, view.controls.sel_arch, height=450),
        use_container_width=True,
    )


def _render_map(view: View) -> None:
    gdf, hover, unmatched = join_to_boundaries(view)

    if gdf is not None and len(gdf):
        col_map, col_load = st.columns([5, 3])
        col_map.plotly_chart(choropleth_fig(gdf, view, hover), use_container_width=True)
        col_load.plotly_chart(
            loadings_bar(view.endmembers, view.controls.sel_arch, height=650),
            use_container_width=True,
        )
        if view.controls.value_kind != "Archetype abundance":
            shows = ("the dominant archetype"
                     if view.controls.value_kind == "Dominant archetype" else "turnout")
            col_load.caption(
                "Loadings of the archetype selected in the sidebar "
                f"(the map itself shows {shows})."
            )

    render_unmatched(unmatched)
