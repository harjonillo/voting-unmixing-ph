"""Loaders for the preprocessed 2025-PH-elections datasets (see data/README.md)."""

import numpy as np
import pandas as pd

from src.config import data_path


def load_complete(config, section: str = "2025-senators") -> pd.DataFrame:
    """Load the per-clustered-precinct results table (geography + stats + votes).

    Drops the stray index column and rows with any NaN, matching the notebooks.
    """
    path = data_path(config, config[section]["file_complete"])
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", axis=1)
    return df.dropna(axis=0)


def load_matlab_results(config, section: str = "2025-senators"):
    """Load the MATLAB unmixing outputs: mixing matrix M and abundance matrix S.

    Y ≈ M @ S with M (candidates x archetypes), S (archetypes x precincts).
    Row/column alignment with the CSVs is NOT guaranteed — use only for
    qualitative comparison (as in the original eda/visualizer notebooks).
    """
    file_spectra = data_path(config, config[section]["file_spectra"])
    file_abundance = data_path(config, config[section]["file_abundance"])
    M = pd.read_csv(file_spectra, sep="\t", header=None).to_numpy()
    S = pd.read_csv(file_abundance, sep="\t", header=None).to_numpy()
    return M, S


def save_processed(pre, endmembers: np.ndarray, abundances: np.ndarray, meta: dict, config):
    """Write the pipeline outputs the app and notebooks read.

    - endmembers.csv    candidates (rows, labelled) x archetypes
    - abundances.parquet  one row per precinct: geography/info columns + one
      column per archetype ("arch_0", ...) — row-aligned by construction
    - meta.json         parameters + fit metrics
    """
    import json

    from src.config import processed_path

    out = processed_path(config)
    out.mkdir(parents=True, exist_ok=True)

    p = endmembers.shape[1]
    arch_cols = [f"arch_{j}" for j in range(p)]

    pd.DataFrame(
        endmembers, index=pre.candidate_labels, columns=arch_cols
    ).rename_axis("candidate").to_csv(out / "endmembers.csv")

    df_ab = pre.df_geo.reset_index(drop=True).copy()
    for j, col in enumerate(arch_cols):
        df_ab[col] = abundances[j, :]
    df_ab.to_parquet(out / "abundances.parquet", index=False)

    with open(out / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    return out


def load_processed(config):
    """Load the pipeline outputs written by ``save_processed``."""
    import json

    from src.config import processed_path

    out = processed_path(config)
    endmembers = pd.read_csv(out / "endmembers.csv", index_col="candidate")
    abundances = pd.read_parquet(out / "abundances.parquet")
    with open(out / "meta.json") as f:
        meta = json.load(f)
    return endmembers, abundances, meta
