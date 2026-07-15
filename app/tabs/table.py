"""Aggregated-values table tab."""

import streamlit as st

from app.components.constants import LEVEL_LABELS
from app.components.data import View


def render(view: View) -> None:
    level = view.controls.level
    st.subheader(f"Aggregated values — {LEVEL_LABELS[level]} level")
    st.dataframe(view.agg, use_container_width=True, height=600)
    st.download_button(
        "Download CSV",
        view.agg.to_csv(index=False).encode(),
        file_name=f"abundances_{level}.csv",
        mime="text/csv",
    )
