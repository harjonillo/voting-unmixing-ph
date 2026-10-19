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


def method_path(
    config: configparser.ConfigParser, method: str, *parts: Union[str, Path]
) -> Path:
    """Absolute path inside one extraction method's processed-outputs folder.

    MVSA (the original method) keeps the top of ``processed_path``; every other
    method gets its own subfolder (``processed_path``/<method>/), with the same
    layout inside (endmembers.csv, abundances.parquet, meta.json, sweep/).

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
    if method == "mvsa":
        return processed_path(config, *parts)
    return processed_path(config, method, *parts)


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
