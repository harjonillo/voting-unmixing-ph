"""Cached access to the pipeline artifacts, and the aggregation derived from
the sidebar selections that every tab reads.
"""

from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from app.components.constants import BALLOT_COL, REGISTERED_COL, VOTERS_COL
from app.components.sidebar import Controls
from src.aggregation import aggregate_abundances, dominant_archetype
from src.config import load_config
from src.data.loading import load_processed, load_sweep
from src.geo import canonical_province, load_municipalities, load_provinces

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
    df["PROV_KEY"] = [
        canonical_province(pr, rg) for pr, rg in zip(df["PROVINCE"], df["REGION"])
    ]
    for c in arch_cols_p:
        df[c + "_w"] = df[c] * df[BALLOT_COL]
    g = df.groupby(["trial", "PROV_KEY"], observed=True).sum(numeric_only=True)
    per_trial = pd.DataFrame(
        {c: g[c + "_w"] / g[BALLOT_COL] for c in arch_cols_p}
    ).reset_index()
    mean = per_trial.groupby("PROV_KEY")[arch_cols_p].mean()
    std = per_trial.groupby("PROV_KEY")[arch_cols_p].std(ddof=1)
    return mean, std


# ---------------------------------------------------------------------------
# Derived view
# ---------------------------------------------------------------------------


def add_turnout(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `turnout_pct` column in place when the voter counts are present."""
    if VOTERS_COL in df.columns and REGISTERED_COL in df.columns:
        df["turnout_pct"] = 100 * df[VOTERS_COL] / df[REGISTERED_COL]
    return df


VALUE_KINDS = ["Archetype abundance", "Dominant archetype", "Turnout"]


def resolve_value(value_kind: str, sel_arch: str) -> tuple[str, str]:
    """(column of `agg` to color by, colorbar title) for a quantity choice."""
    if value_kind == "Archetype abundance":
        return sel_arch, f"mean abundance ({sel_arch})"
    if value_kind == "Dominant archetype":
        return "dominant", "dominant archetype"
    return "turnout_pct", "turnout (%)"


@dataclass
class View:
    """The loaded artifacts plus the aggregation implied by `controls`.

    Tabs read this rather than recomputing; it is rebuilt on every rerun.

    `value_col`/`colorbar` are the map's quantity choice. That control now
    lives inside the tab, which renders after `build_view` has run, so the
    view is built with a default and the tab calls `with_value()` to get a
    copy carrying its own selection.
    """

    endmembers: pd.DataFrame
    abundances: pd.DataFrame  # all precincts, before the region filter
    meta: dict
    controls: Controls
    df_ab: pd.DataFrame  # precincts after the region filter
    agg: pd.DataFrame  # df_ab aggregated to controls.level
    value_col: str = "dominant"  # column of `agg` the map colors by
    colorbar: str = "dominant archetype"

    def with_value(self, value_kind: str, sel_arch: str) -> "View":
        """A copy colored by `value_kind` (shares the underlying frames)."""
        value_col, colorbar = resolve_value(value_kind, sel_arch)
        return replace(self, value_col=value_col, colorbar=colorbar)

    @property
    def arch_cols(self) -> list[str]:
        return list(self.endmembers.columns)

    @property
    def n_arch(self) -> int:
        return len(self.endmembers.columns)

    @property
    def candidate_labels(self) -> list[str]:
        return list(self.endmembers.index)


def build_view(
    endmembers: pd.DataFrame,
    abundances: pd.DataFrame,
    meta: dict,
    controls: Controls,
) -> View:
    arch_cols = list(endmembers.columns)

    df_ab = abundances

    agg = aggregate_abundances(
        df_ab,
        level=controls.level,
        weight_col=controls.weight_col,
    )
    agg["dominant"] = dominant_archetype(agg, arch_cols) if len(agg) else []
    add_turnout(agg)

    # No value_col here: the quantity is chosen inside the map tab, which
    # renders later — see View.with_value().
    return View(
        endmembers=endmembers,
        abundances=abundances,
        meta=meta,
        controls=controls,
        df_ab=df_ab,
        agg=agg,
    )
