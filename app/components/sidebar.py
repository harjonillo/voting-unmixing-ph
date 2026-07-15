"""Sidebar controls — the single place user selections enter the app."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from app.components.constants import BALLOT_COL, LEVEL_LABELS, arch_label


@dataclass
class Controls:
    """The current sidebar selections."""

    level: str
    value_kind: str
    sel_arch: str
    weighted: bool
    region_filter: list[str]

    @property
    def weight_col(self) -> str | None:
        """Weight column for `aggregate_abundances`, or None for a plain mean."""
        return BALLOT_COL if self.weighted else None


def render_sidebar(abundances: pd.DataFrame, arch_cols: list[str], meta: dict) -> Controls:
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
        format_func=arch_label,
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

    return Controls(
        level=level,
        value_kind=value_kind,
        sel_arch=sel_arch,
        weighted=weighted,
        region_filter=region_filter,
    )
