"""Aggregate per-precinct quantities to national / region / province /
municipality / clustered-precinct level."""

from typing import List, Optional

import numpy as np
import pandas as pd

LEVEL_COLS = {
    "national": [],
    "region": ["REGION"],
    "province": ["REGION", "PROVINCE"],
    "municipality": ["REGION", "PROVINCE", "CITY_MUNICIPALITY"],
    "barangay": ["REGION", "PROVINCE", "CITY_MUNICIPALITY", "BARANGAY"],
}

LEVELS = list(LEVEL_COLS)


def aggregate_abundances(
    df_ab: pd.DataFrame,
    level: str = "region",
    arch_cols: Optional[List[str]] = None,
    weight_col: Optional[str] = "information.numberOfValidBallot",
) -> pd.DataFrame:
    """Mean archetype abundance per geographic unit.

    Parameters
    ----------
    df_ab : pandas.DataFrame, shape (N, n_geo + p)
        Abundances table: one row per precinct, with geography/info
        columns and one ``arch_*`` column per archetype, e.g. from
        ``src.data.load_processed``.
    level : {'national', 'region', 'province', 'municipality', 'barangay'}, default 'region'
        Geographic level to aggregate to (see ``LEVEL_COLS``).
    arch_cols : list of str, optional
        Abundance columns to aggregate; defaults to every column starting
        with ``'arch_'``.
    weight_col : str or None, default 'information.numberOfValidBallot'
        Column used as weights (voter-weighted mean); None for an
        unweighted mean over precincts.

    Returns
    -------
    pandas.DataFrame
        One row per geographic unit: the grouping columns, the (weighted)
        mean abundance per archetype, ``n_precincts``, and — when the
        columns exist — summed voter/ballot counts.

    Raises
    ------
    ValueError
        If `level` is not one of ``LEVELS``.
    """
    if level not in LEVEL_COLS:
        raise ValueError(f"level must be one of {LEVELS}")
    if arch_cols is None:
        arch_cols = [c for c in df_ab.columns if c.startswith("arch_")]

    group_cols = LEVEL_COLS[level]
    count_cols = [
        c
        for c in (
            "information.numberOfRegisteredVoters",
            "information.numberOfActuallyVoters",
            "information.numberOfValidBallot",
        )
        if c in df_ab.columns
    ]

    def _summarize(g: pd.DataFrame) -> pd.Series:
        out = {}
        if weight_col is not None and weight_col in g.columns:
            w = g[weight_col].to_numpy(dtype=float)
            w_sum = w.sum()
            for c in arch_cols:
                out[c] = (
                    float((g[c].to_numpy() * w).sum() / w_sum) if w_sum > 0 else np.nan
                )
        else:
            for c in arch_cols:
                out[c] = float(g[c].mean())
        out["n_precincts"] = len(g)
        for c in count_cols:
            out[c] = float(g[c].sum())
        return pd.Series(out)

    if not group_cols:  # national
        return _summarize(df_ab).to_frame().T

    agg = (
        df_ab.groupby(group_cols, observed=True)
        .apply(_summarize, include_groups=False)
        .reset_index()
    )
    agg["n_precincts"] = agg["n_precincts"].astype(int)
    return agg


def dominant_archetype(
    agg: pd.DataFrame, arch_cols: Optional[List[str]] = None
) -> np.ndarray:
    """Index of the highest-abundance archetype per row of an aggregated table.

    Parameters
    ----------
    agg : pandas.DataFrame
        Aggregated abundances (one row per geographic unit), e.g. from
        `aggregate_abundances`.
    arch_cols : list of str, optional
        Abundance columns to compare; defaults to every column starting
        with ``'arch_'``.

    Returns
    -------
    ndarray of int, shape (n_rows,)
        For each row of `agg`, the position (0-based, within `arch_cols`)
        of the archetype with the highest abundance.
    """
    if arch_cols is None:
        arch_cols = [c for c in agg.columns if c.startswith("arch_")]
    return agg[arch_cols].to_numpy().argmax(axis=1)
