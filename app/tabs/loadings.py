"""Endmember loadings tab."""

import streamlit as st

from app.components.charts import loadings_bar
from app.components.constants import arch_label
from app.components.data import View


def render(view: View) -> None:
    st.subheader("Endmember (archetype) loadings")
    st.caption("Candidate weights per archetype from MVSA — a national-level "
               "property of the unmixing, independent of the aggregation level.")

    top_n = st.slider("Top N candidates", 5, len(view.candidate_labels), 15)
    which = st.multiselect(
        "Archetypes", view.arch_cols, default=view.arch_cols,
        format_func=arch_label,
    )

    ncols = min(3, max(1, len(which)))
    cols = st.columns(ncols)
    for i, c in enumerate(which):
        fig = loadings_bar(view.endmembers, c, top_n, title=arch_label(c))
        cols[i % ncols].plotly_chart(fig, use_container_width=True)
