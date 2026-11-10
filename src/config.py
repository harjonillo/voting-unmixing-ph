"""Config loading. Paths in configs/config.ini are relative to the repo root."""

import configparser
from pathlib import Path
from typing import Optional, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "config.ini"


def load_config(path: Optional[Union[str, Path]] = None) -> configparser.ConfigParser:
    """Read an INI config file.

    Parameters
    ----------
    path : str or pathlib.Path, optional
        Config file to read; defaults to ``configs/config.ini`` in the
        repo root.

    Returns
    -------
    configparser.ConfigParser
        The parsed config.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    """
    config = configparser.ConfigParser()
    read = config.read(path or DEFAULT_CONFIG)
    if not read:
        raise FileNotFoundError(f"Config file not found: {path or DEFAULT_CONFIG}")
    return config


def data_path(config: configparser.ConfigParser, *parts: Union[str, Path]) -> Path:
    """Absolute path inside the data folder.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; ``[DEFAULT] data_path`` names the folder.
    *parts : str or pathlib.Path
        Path components appended below the data folder.

    Returns
    -------
    pathlib.Path
        The absolute path.
    """
    return REPO_ROOT / config["DEFAULT"]["data_path"] / Path(*parts)


def processed_path(config: configparser.ConfigParser, *parts: Union[str, Path]) -> Path:
    """Absolute path inside the processed-outputs folder.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; ``[DEFAULT] processed_path`` names the folder.
    *parts : str or pathlib.Path
        Path components appended below the processed folder.

    Returns
    -------
    pathlib.Path
        The absolute path.
    """
    return REPO_ROOT / config["DEFAULT"]["processed_path"] / Path(*parts)


# Normalizations whose denominator counts ballots (voters); mirrors
# src.data.preprocessing.PER_BALLOT_NORMALIZATIONS (not imported, to keep this
# module free of the data stack).
PER_BALLOT_NORMALIZATIONS = ("valid_ballots", "actual_voters")


def normalization(config: configparser.ConfigParser) -> str:
    """The config's ``[preprocessing] normalization``."""
    return config["preprocessing"]["normalization"]


def set_normalization(
    config: configparser.ConfigParser, norm: Optional[str]
) -> configparser.ConfigParser:
    """Override the config's normalization in place (no-op for None); returns
    the config. Every script's ``--normalization`` flag goes through this, so
    preprocessing and all output paths follow the override."""
    if norm:
        config["preprocessing"]["normalization"] = norm
    return config


def norm_subdir(config: configparser.ConfigParser) -> str:
    """Output subfolder for the config's normalization: "" for the per-ballot
    normalizations (the original layout), else the normalization's name
    (e.g. "vote_sum")."""
    norm = normalization(config)
    return "" if norm in PER_BALLOT_NORMALIZATIONS else norm


def run_subdir(config: configparser.ConfigParser, method: str) -> Path:
    """<norm_subdir>/<method> below an output root, each part omitted when
    default (per-ballot normalization; MVSA). Shared by the processed outputs,
    the bake scripts' outputs and caches, and the site data tree."""
    parts = [norm_subdir(config)] + ([] if method == "mvsa" else [method])
    return Path(*[p for p in parts if p]) if any(parts) else Path()


def method_path(
    config: configparser.ConfigParser, method: str, *parts: Union[str, Path]
) -> Path:
    """Absolute path inside one (normalization, extraction method) run's
    processed-outputs folder.

    Per-ballot MVSA (the original run) keeps the top of ``processed_path``;
    other normalizations get a subfolder named after them, and other methods a
    subfolder below that (``processed_path``/[vote_sum/][nmf/]), with the same
    layout inside (endmembers.csv, abundances.parquet, meta.json, sweep/). See
    ``run_subdir``.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; ``[DEFAULT] processed_path`` names the folder.
    method : str
        Extraction method key ("mvsa", "nmf", ...).
    *parts : str or pathlib.Path
        Path components appended below the method's folder.

    Returns
    -------
    pathlib.Path
        The absolute path.
    """
    return processed_path(config, run_subdir(config, method), *parts)


def shapefile_path(config: configparser.ConfigParser, *parts: Union[str, Path]) -> Path:
    """Absolute path inside the shapefile folder.

    Parameters
    ----------
    config : configparser.ConfigParser
        Loaded config; ``[DEFAULT] shapefile_path`` names the folder.
    *parts : str or pathlib.Path
        Path components appended below the shapefile folder.

    Returns
    -------
    pathlib.Path
        The absolute path.
    """
    return REPO_ROOT / config["DEFAULT"]["shapefile_path"] / Path(*parts)
