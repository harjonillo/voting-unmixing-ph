"""Loaders for the preprocessed 2025-PH-elections datasets (see data/README.md)."""

import configparser
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Tuple

import numpy as np
import pandas as pd

from src.config import data_path

if TYPE_CHECKING:
    from src.data.preprocessing import PreprocessedData


def load_complete(config: configparser.ConfigParser) -> pd.DataFrame:
    """Load the per-clustered-precinct results table (geography + stats + votes).

    Reads the senatorial-votes CSV named in the ``[elections]`` config section.
    Drops the stray index column, any entirely-empty column (e.g. 2019's
    unused ``information.abstentions``, which is all-NaN), then rows with any
    remaining NaN, matching the notebooks.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config whose ``[elections]`` section names the
        ``senatorial_votes_file``.

    Returns
    -------
    pandas.DataFrame
        One row per clustered precinct: geography columns, information
        columns, and one vote-count column per candidate.
    """
    path = data_path(config, config["elections"]["senatorial_votes_file"])
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", axis=1)
    # Drop all-NaN columns first so one unused empty column (2019 abstentions)
    # does not cause dropna(axis=0) to discard every row.
    df = df.dropna(axis=1, how="all")
    return df.dropna(axis=0)


def save_processed(
    pre: "PreprocessedData",
    endmembers: np.ndarray,
    abundances: np.ndarray,
    meta: dict,
    config: configparser.ConfigParser,
) -> Path:
    """Write the pipeline outputs the app and notebooks read.

    - endmembers.csv    candidates (rows, labelled) x archetypes
    - abundances.parquet  one row per precinct: geography/info columns + one
      column per archetype ("arch_0", ...) — row-aligned by construction
    - meta.json         parameters + fit metrics

    Parameters
    ----------
    pre : PreprocessedData
        Preprocessing output; supplies ``candidate_labels`` (row index of
        endmembers.csv) and ``df_geo`` (abundances.parquet geography).
    endmembers : ndarray, shape (L, p)
        Endmember (mixing) matrix: L candidates (rows, aligned with
        ``pre.candidate_labels``) x p archetypes (columns).
    abundances : ndarray, shape (p, N)
        Abundance matrix: p archetypes (rows) x N precincts (columns,
        aligned with the rows of ``pre.df_geo``).
    meta : dict
        Run parameters and fit metrics, JSON-serialized as-is.
    config : configparser.ConfigParser
        Loaded config; its ``processed_path`` names the output folder.

    Returns
    -------
    pathlib.Path
        The output directory the three files were written to.
    """
    import json

    from src.config import processed_path

    out = processed_path(config)
    out.mkdir(parents=True, exist_ok=True)

    p = endmembers.shape[1]
    arch_cols = [f"arch_{j}" for j in range(p)]

    pd.DataFrame(endmembers, index=pre.candidate_labels, columns=arch_cols).rename_axis(
        "candidate"
    ).to_csv(out / "endmembers.csv")

    df_ab = pre.df_geo.reset_index(drop=True).copy()
    for j, col in enumerate(arch_cols):
        df_ab[col] = abundances[j, :]
    df_ab.to_parquet(out / "abundances.parquet", index=False)

    with open(out / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    return out


def load_processed(
    config: configparser.ConfigParser,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load the pipeline outputs written by ``save_processed``.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; its ``processed_path`` names the folder to read.

    Returns
    -------
    endmembers : pandas.DataFrame, shape (L, p)
        Endmember matrix: L candidates (rows, indexed by candidate label)
        x p archetypes (columns ``arch_0`` ... ``arch_{p-1}``).
    abundances : pandas.DataFrame, shape (N, n_geo + p)
        One row per precinct: geography/info columns plus one abundance
        column per archetype. NOTE this is the transpose orientation of
        the (p, N) abundance matrices used by the unmixing code.
    meta : dict
        Run parameters and fit metrics.
    """
    import json

    from src.config import processed_path

    out = processed_path(config)
    endmembers = pd.read_csv(out / "endmembers.csv", index_col="candidate")
    abundances = pd.read_parquet(out / "abundances.parquet")
    with open(out / "meta.json") as f:
        meta = json.load(f)
    return endmembers, abundances, meta


def load_sweep(
    config: configparser.ConfigParser, full_resolution: bool = False
) -> Dict[int, dict]:
    """Load the endmember-count sweep written by ``scripts/run_sweep.py``.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; the sweep lives under ``processed_path``/sweep.
    full_resolution : bool, default False
        Also load the per-precinct reference abundances
        (``abundances_ref``), which are much larger than the aggregates.

    Returns
    -------
    dict of {int: dict}
        Keyed by endmember count p. Each entry has ``loadings_mean`` and
        ``loadings_std`` ((L, p) DataFrames indexed by candidate, one
        column per archetype), ``agg_trials`` (per-trial municipality
        aggregates), ``meta`` (dict), and — when `full_resolution` —
        ``abundances_ref`` (one row per precinct, one column per
        archetype). Empty dict if the sweep has not been run.
    """
    import json

    from src.config import processed_path

    root = processed_path(config, "sweep")
    out = {}
    if not root.exists():
        return out
    for sub in sorted(root.glob("p*")):
        try:
            p = int(sub.name[1:])
        except ValueError:
            continue
        entry = {
            "loadings_mean": pd.read_csv(
                sub / "loadings_mean.csv", index_col="candidate"
            ),
            "loadings_std": pd.read_csv(
                sub / "loadings_std.csv", index_col="candidate"
            ),
            "agg_trials": pd.read_parquet(sub / "agg_municipality_trials.parquet"),
        }
        with open(sub / "meta.json") as f:
            entry["meta"] = json.load(f)
        if full_resolution:
            entry["abundances_ref"] = pd.read_parquet(sub / "abundances_ref.parquet")
        out[p] = entry
    return out
