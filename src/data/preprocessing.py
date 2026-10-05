"""Precinct/candidate filtering and vote-matrix construction.

Consolidates the preprocessing that was repeated across the 2025-PH-elections
notebooks (analysis_elections_2025, trials_elections_2025_*), using the most
recent version (trial-clustering notebook) as the reference:

1. drop excluded regions (overseas OV, local absentee LAV),
2. keep candidates whose 25th percentile of per-precinct votes >= threshold,
3. keep precincts with >= threshold total votes over the kept candidates,
4. rank candidates by national total votes,
5. normalize each precinct's votes (valid ballots / row max / none).
"""

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

GEO_COLS = [
    "REGION",
    "PROVINCE",
    "CITY_MUNICIPALITY",
    "BARANGAY",
]

INFO_COLS = [
    "information.numberOfRegisteredVoters",
    "information.numberOfActuallyVoters",
    "information.numberOfValidBallot",
    "information.turnout",
]

NORMALIZATIONS = ("valid_ballots", "row_max", "none")


@dataclass
class PreprocessedData:
    """Vote matrix plus the row-aligned geography table.

    Column j of ``Y`` corresponds to row j of ``df_geo``.
    """

    Y_raw: np.ndarray                  # (L candidates, N precincts)
    Y: np.ndarray                      # (L candidates, N precincts)
    df_geo: pd.DataFrame               # N rows: GEO_COLS + INFO_COLS
    ranked_columns: List[str]          # original CSV column names, by national rank
    candidate_labels: List[str]        # "SURNAME, NAME (PARTY) [rank]"
    params: dict = field(default_factory=dict)

    @property
    def n_candidates(self):
        """Number of kept candidates (rows of ``Y``)."""
        return self.Y.shape[0]

    @property
    def n_precincts(self):
        """Number of kept precincts (columns of ``Y``)."""
        return self.Y.shape[1]


def candidate_label(column: str, rank: int) -> str:
    """Build a display label from a CSV candidate column name and a rank.

    Parameters
    ----------
    column : str
        Original CSV column header, e.g. ``'12. SURNAME, NAME (PARTY)'``;
        the ballot number before the first '.' is dropped and whitespace
        (including embedded newlines) is collapsed.
    rank : int
        National rank by total votes (1 = most voted).

    Returns
    -------
    label : str
        ``'SURNAME, NAME (PARTY) [rank]'``.
    """
    name = column.split(".", 1)[1].strip() if "." in column else column
    name = " ".join(name.split())  # collapse the newline/extra spaces in headers
    return f"{name} [{rank}]"


def preprocess(
    df: pd.DataFrame,
    excluded_regions=("OV", "LAV", "OAV"),
    sen_col_start: int = 17,
    min_candidate_25th_percentile: float = 10,
    min_precinct_votes: float = 10,
    normalization: str = "valid_ballots",
    randomize_precinct_order: bool = False,
    verbose: bool = True,
) -> PreprocessedData:
    """Filter, rank, and normalize the raw results table into a vote matrix.

    Applies the five steps listed in the module docstring: drop excluded
    regions, keep candidates by 25th-percentile votes, keep precincts by
    total votes, rank candidates by national total, normalize per precinct.

    Parameters
    ----------
    df : pandas.DataFrame
        Per-clustered-precinct results table (geography + stats + one column
        per candidate), as returned by ``load_complete``.
    excluded_regions : sequence of str, default ('OV', 'LAV', 'OAV')
        REGION codes dropped before any filtering (overseas/absentee).
    sen_col_start : int, default 17
        Index of the first senatorial-candidate column in `df`.
    min_candidate_25th_percentile : float, default 10
        Candidate kept only if the 25th percentile of its per-precinct votes
        is at least this.
    min_precinct_votes : float, default 10
        Precinct kept only if its total votes over the kept candidates is at
        least this.
    normalization : {'valid_ballots', 'row_max', 'none'}, default 'valid_ballots'
        Per-precinct denominator for the vote counts.
    randomize_precinct_order : bool, default False
        If True, shuffle the kept precincts (columns of ``Y`` and rows of
        ``df_geo``, which stay aligned) using the global NumPy RNG — seed
        with ``np.random.seed`` beforehand for reproducibility. Used by
        notebook 09's order-sensitivity trials.
    verbose : bool, default True
        Print the candidate/precinct counts before and after filtering.

    Returns
    -------
    PreprocessedData
        Vote matrices ``Y_raw``/``Y`` (L candidates x N precincts), the
        row-aligned geography table, ranked column names and labels, and a
        ``params`` dict recording the settings plus ``precinct_ids`` — the
        original `df` row labels in final column order, which lets callers
        map a shuffled run's precincts back onto another run's order.

    Raises
    ------
    ValueError
        If `normalization` is unknown, or a kept precinct has a zero
        normalization denominator.
    """
    if normalization not in NORMALIZATIONS:
        raise ValueError(f"normalization must be one of {NORMALIZATIONS}")

    df = df[~df["REGION"].isin(list(excluded_regions))].copy()
    candidate_cols = df.columns[sen_col_start:]

    pct25 = df[candidate_cols].describe().loc["25%"]
    kept_candidates = pct25[pct25 >= min_candidate_25th_percentile].index.tolist()

    precinct_totals = df[kept_candidates].sum(axis=1)
    kept_precincts = precinct_totals[precinct_totals >= min_precinct_votes].index

    if randomize_precinct_order:
        kept_precincts = np.random.permutation(kept_precincts)

    can_totals = df.loc[kept_precincts, kept_candidates].sum().sort_values(ascending=False)
    ranked_columns = list(can_totals.index)
    labels = [candidate_label(c, r) for r, c in enumerate(ranked_columns, 1)]

    vote_raw = df.loc[kept_precincts, ranked_columns].values.astype(float)

    if normalization == "valid_ballots":
        denom = df.loc[kept_precincts, "information.numberOfValidBallot"].values.reshape(-1, 1)
    elif normalization == "row_max":
        denom = vote_raw.max(axis=1, keepdims=True)
    else:
        denom = np.ones((vote_raw.shape[0], 1))
    if np.any(denom == 0):
        raise ValueError("Zero normalization denominator for some precincts.")

    Y = (vote_raw / denom).T

    keep_cols = [c for c in GEO_COLS + INFO_COLS if c in df.columns]
    df_geo = df.loc[kept_precincts, keep_cols].reset_index(drop=True)

    params = {
        "excluded_regions": list(excluded_regions),
        "sen_col_start": sen_col_start,
        "min_candidate_25th_percentile": min_candidate_25th_percentile,
        "min_precinct_votes": min_precinct_votes,
        "normalization": normalization,
        "randomize_precinct_order": randomize_precinct_order,
        "n_candidates_before": len(candidate_cols),
        "n_precincts_before": len(df),
        # original df row labels in final column order of Y — lets callers map
        # a (possibly shuffled) run's precincts back onto another run's order
        "precinct_ids": np.asarray(kept_precincts),
    }

    if verbose:
        print(f"candidates: {len(candidate_cols)} -> {len(kept_candidates)} "
              f"(25th pct >= {min_candidate_25th_percentile})")
        print(f"precincts:  {len(df):,} -> {len(kept_precincts):,} "
              f"(total votes >= {min_precinct_votes})")
        print(f"Y: {Y.shape[0]} candidates x {Y.shape[1]:,} precincts "
              f"({normalization} normalization)")

    return PreprocessedData(Y_raw=vote_raw.T, Y=Y, df_geo=df_geo, ranked_columns=ranked_columns,
                            candidate_labels=labels, params=params)


def preprocess_from_config(df: pd.DataFrame, config, randomize_precinct_order: bool = False,
                           verbose: bool = True) -> PreprocessedData:
    """Run `preprocess` with the [preprocessing] section of the config.

    Parameters
    ----------
    df : pandas.DataFrame
        Per-clustered-precinct results table, as returned by ``load_complete``.
    config : configparser.ConfigParser
        Loaded config whose ``[preprocessing]`` section supplies the
        filtering and normalization settings.
    randomize_precinct_order : bool, default False
        Passed through to `preprocess`; shuffles the kept precincts using
        the global NumPy RNG.
    verbose : bool, default True
        Passed through to `preprocess`.

    Returns
    -------
    PreprocessedData
        See `preprocess`.
    """
    sec = config["preprocessing"]
    excluded = [r.strip() for r in sec["excluded_regions"].split(",") if r.strip()]
    return preprocess(
        df,
        excluded_regions=excluded,
        sen_col_start=sec.getint("sen_col_start"),
        min_candidate_25th_percentile=sec.getfloat("min_candidate_25th_percentile"),
        min_precinct_votes=sec.getfloat("min_precinct_votes"),
        normalization=sec.get("normalization"),
        randomize_precinct_order=randomize_precinct_order,
        verbose=verbose,
    )
