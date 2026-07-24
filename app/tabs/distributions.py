"""Abundance distributions tab."""

import streamlit as st

from app.components import theme
from app.components.charts import abundance_histogram
from app.components.constants import LEVEL_LABELS
from app.components.data import View


def render(view: View) -> None:
    level = view.controls.level
    st.subheader(f"Abundance distributions — {LEVEL_LABELS[level]} level")

    if level == "national":
        source, unit = view.df_ab, "precinct"
    else:
        source, unit = view.agg, LEVEL_LABELS[level].lower()

    ncols = min(4, view.n_arch)
    cols = st.columns(ncols)
    for j, c in enumerate(view.arch_cols):
        cols[j % ncols].plotly_chart(
            abundance_histogram(
                source, c, unit, color=theme.archetype_color(c, view.n_arch)
            ),
            use_container_width=True,
        )
