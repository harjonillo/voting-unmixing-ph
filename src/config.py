"""Config loading. Paths in configs/config.ini are relative to the repo root."""

import configparser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "config.ini"


def load_config(path=None) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    read = config.read(path or DEFAULT_CONFIG)
    if not read:
        raise FileNotFoundError(f"Config file not found: {path or DEFAULT_CONFIG}")
    return config


def data_path(config, *parts) -> Path:
    """Absolute path inside the data folder."""
    return REPO_ROOT / config["DEFAULT"]["data_path"] / Path(*parts)


def processed_path(config, *parts) -> Path:
    return REPO_ROOT / config["DEFAULT"]["processed_path"] / Path(*parts)


def shapefile_path(config, *parts) -> Path:
    return REPO_ROOT / config["DEFAULT"]["shapefile_path"] / Path(*parts)
