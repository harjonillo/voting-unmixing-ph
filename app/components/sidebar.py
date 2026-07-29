"""Sidebar controls for global user selections"""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from app.components.constants import BALLOT_COL, LEVEL_LABELS, arch_label


@dataclass
class Controls:
    """The current sidebar selections."""

    level: str
    top_n: int
    weighted: bool

    @property
    def weight_col(self) -> str | None:
        """Weight column for `aggregate_abundances`, or None for a plain mean."""
        return BALLOT_COL if self.weighted else None


def render_sidebar(
    abundances: pd.DataFrame, arch_cols: list[str], meta: dict
) -> Controls:
    st.sidebar.title("PH voting archetypes")
    st.sidebar.caption(
        f"2025 senatorial race with {meta['n_archetypes']} endmembers, "
        f"{len(abundances):,} clustered precincts "
    )

    level = st.sidebar.radio(
        "Aggregation level",
        list(LEVEL_LABELS),
        format_func=LEVEL_LABELS.get,
        index=1,
    )

    top_n = st.sidebar.number_input(
        "Top N candidates", min_value=3, max_value=15, value=5, step=1
    )

    weighted = st.sidebar.checkbox(
        "Weight means by valid ballots",
        value=True,
        help="Off = plain mean over precincts",
    )

    return Controls(
        level=level,
        top_n=top_n,
        weighted=weighted,
    )
