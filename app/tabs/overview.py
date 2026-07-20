"""Map / overview tab."""

import plotly.express as px
import streamlit as st

from app.components import theme
from app.components.charts import loadings_bar
from app.components.constants import arch_label
from app.components.data import View
from app.components.map import choropleth_fig, join_to_boundaries, render_unmatched

def render(view: View) -> None:

    if view.controls.level == "clustered_precinct":
        st.info(
            "Clustered precincts have no boundary geometry — see the "
            "distribution and table tabs; the map is available down to the "
            "municipality level."
        )
        st.dataframe(view.agg.head(1000), use_container_width=True)
    else:
        col_0, col_1 = st.columns([2, 3])
        _render_map(col_0, view)
        _render_endmembers(col_1, view)


def _render_endmembers(col_1: st.container, view: View) -> None:

    row = view.agg.iloc[0]
    
    with col_1:
        st.subheader("Endmember (archetype) loadings")
        st.caption("Candidate weights per archetype from MVSA — a national-level "
                "property of the unmixing, independent of the aggregation level.")


        ncols = min(3, max(1, len(view.controls.which_arch)))
        cols = st.columns(ncols)
        for i, c in enumerate(view.controls.which_arch):
            fig = loadings_bar(view.endmembers, c, view.controls.top_n, title=arch_label(c),
                               color=theme.archetype_color(c, view.n_arch))
            cols[i % ncols].plotly_chart(fig, use_container_width=True)

    


def _render_map(col_0: st.container, view: View) -> None:
    with col_0:
        st.subheader(f"Endmember {view.controls.value_kind.lower()} by {view.controls.level}")
        gdf, hover, unmatched = join_to_boundaries(view)

        if gdf is not None and len(gdf):
            st.plotly_chart(
                choropleth_fig(gdf, view, hover), 
                use_container_width=True
            )
