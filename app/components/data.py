"""Cached access to the pipeline artifacts, and the aggregation derived from
the sidebar selections that every tab reads.
"""

from dataclasses import dataclass, replace

import pandas as pd
import streamlit as st

from app.components.constants import BALLOT_COL, REGISTERED_COL, VOTERS_COL
from app.components.sidebar import Controls
from src.aggregation import LEVEL_COLS, aggregate_abundances, dominant_archetype
from src.config import REPO_ROOT, load_config
from src.data.loading import load_processed, load_sweep
from src.geo import load_municipalities, load_provinces
from src.unmixing.matching import match_to_reference

# Grouping columns present in each per-trial municipality aggregate (written by
# scripts/run_sweep.py). Used to collapse trials back to one row per municipality.
MUNI_COLS = ["REGION", "PROVINCE", "CITY_MUNICIPALITY"]

# Election years selectable in the app. Each needs a configs/config_<year>.ini
# and its processed artifacts under data/processed/<year>/.
AVAILABLE_YEARS = ["2025", "2022", "2019"]
DEFAULT_YEAR = AVAILABLE_YEARS[0]

# ---------------------------------------------------------------------------
# Cached loading
# ---------------------------------------------------------------------------


def config_for_year(year: str):
    """Load the per-year config (configs/config_<year>.ini)."""
    return load_config(REPO_ROOT / "configs" / f"config_{year}.ini")


@st.cache_data
def get_processed(year: str):
    endmembers, abundances, meta = load_processed(config_for_year(year))
    return endmembers, abundances, meta


# Boundaries are shared across years, so they are loaded once from any config.
@st.cache_resource
def get_provinces():
    return load_provinces(config_for_year(DEFAULT_YEAR))


@st.cache_resource
def get_municipalities():
    return load_municipalities(config_for_year(DEFAULT_YEAR))


@st.cache_data
def get_sweep(year: str):
    return load_sweep(config_for_year(year))


@st.cache_data
def endmember_loading_std(year: str):
    """Per-loading std for the overview's endmembers, from the sweep trials.

    The overview shows a single MVSA fit (endmembers.csv); its per-archetype
    uncertainty is the std across the sweep's trials at the same archetype
    count. The sweep is an independent decomposition, so its archetype columns
    are Hungarian-aligned (cosine) to the single fit before the std is borrowed.

    Returns a DataFrame shaped like ``endmembers`` (same index/columns), or
    None when the matching sweep entry is unavailable or the candidate sets
    don't line up.
    """
    endmembers, _, meta = get_processed(year)
    entry = get_sweep(year).get(meta["n_archetypes"])
    if entry is None:
        return None
    mean = entry["loadings_mean"].reindex(endmembers.index)
    std = entry["loadings_std"].reindex(endmembers.index)
    if mean.isna().any().any() or std.isna().any().any():
        return None
    # perm aligns the sweep columns to the single-fit columns:
    # mean.iloc[:, perm] matches endmembers column-wise, so std uses the same perm.
    perm, _ = match_to_reference(endmembers.to_numpy(), mean.to_numpy())
    std_aligned = std.iloc[:, perm]
    std_aligned.columns = endmembers.columns
    return std_aligned


@st.cache_data
def sweep_level_stats(year: str, p: int, level: str, weighted: bool):
    """Mean/std across sweep trials at `level`, plus the trial-mean municipality
    frame, for sweep entry p.

    Each trial's municipality aggregates are re-aggregated to `level`
    (ballot-weighted when `weighted`, matching the main tab's weighting), then
    mean/std are taken across trials. Municipality level needs no
    re-aggregation — there is already one row per municipality per trial.

    Returns (mean_agg, std_agg, mean_muni):
      mean_agg / std_agg  one row per unit at `level`, with the level's grouping
                          columns, arch_* columns (mean / std over trials), and
                          the count columns; identical structure so either can
                          feed the map join.
      mean_muni           one row per municipality (arch means over trials, with
                          summed ballots / precinct counts) — the "precinct
                          table" the region-level join dissolves for geometry.
    """
    entry = get_sweep(year)[p]
    df = entry["agg_trials"]
    arch_cols_p = [c for c in df.columns if c.startswith("arch_")]
    weight_col = BALLOT_COL if weighted else None

    per_trial = []
    for t, g in df.groupby("trial", observed=True):
        a = aggregate_abundances(
            g, level=level, arch_cols=arch_cols_p, weight_col=weight_col
        )
        a["trial"] = t
        per_trial.append(a)
    stacked = pd.concat(per_trial, ignore_index=True).drop(columns="trial")

    group_cols = LEVEL_COLS[level]
    if group_cols:
        grouped = stacked.groupby(group_cols, observed=True)
        # mean_agg carries the (trial-invariant) count columns unchanged; std_agg
        # copies it and overwrites just the arch columns with the trial std.
        mean_agg = grouped.mean(numeric_only=True).reset_index()
        std_only = grouped[arch_cols_p].std(ddof=1).reset_index()
        std_agg = mean_agg.copy()
        for c in arch_cols_p:
            std_agg[c] = std_only[c].to_numpy()
    else:  # national — unused by the sidebar, kept for completeness
        mean_agg = stacked.mean(numeric_only=True).to_frame().T
        std_agg = mean_agg.copy()
        std_agg[arch_cols_p] = stacked[arch_cols_p].std(ddof=1).to_numpy()

    agg_cols = {c: "mean" for c in arch_cols_p}
    agg_cols.update({BALLOT_COL: "first", "n_precincts": "first"})
    mean_muni = (
        df.groupby(MUNI_COLS, observed=True).agg(agg_cols).reset_index()
    )
    return mean_agg, std_agg, mean_muni


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
