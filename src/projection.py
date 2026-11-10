"""2-D projections of the precinct cloud with each method's endmembers.

Shared by scripts/bake_projections.py (the Model comparison tab's "Archetypes in
the precinct cloud" card) and notebook 16, which remakes Fig. 1 of Li &
Bioucas-Dias (2008): precincts projected to two dimensions (PCA or UMAP) with
the VCA, MVSA and NMF endmembers overlaid.

Every expensive step is cached under ``data/notebook_experiments/`` (gitignored),
with the file names notebook 16 and scripts/bake_distinctness.py already use, so
the three share one cache:

- MVSA / NMF endmembers: ``08_distinctness/{normalization}/{year}/
  endm_p{p}_seed{seed}_{params_tag}.npy`` (scripts/bake_distinctness.py);
- VCA endmembers and UMAP fits: ``16_endmember_projections/{year}_{normalization}_
  vca_p{p}_seed{seed}.npy`` and ``..._umap_nn30_md0.1_seed{seed}.pkl``.

UMAP (``umap-learn``) is imported only when a fit is needed: it is a bake-time
dependency, not in requirements.txt.
"""

from __future__ import annotations

import configparser
import contextlib
import io
import pickle
from pathlib import Path

import numpy as np

from .unmixing import extract_endmembers, method_params, vca
from .unmixing.methods import params_tag

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = REPO_ROOT / "data" / "notebook_experiments"
DISTINCTNESS_CACHE = EXPERIMENTS / "08_distinctness"
PROJECTION_CACHE = EXPERIMENTS / "16_endmember_projections"
UMAP_PARAMS = {"n_neighbors": 30, "min_dist": 0.1}


def _norm(config: configparser.ConfigParser) -> str:
    return config["preprocessing"]["normalization"]


def _seed(config: configparser.ConfigParser) -> int:
    return config["unmixing"].getint("seed")


def endmember_cache_path(
    config: configparser.ConfigParser, year: str, p: int, method: str
) -> Path:
    """Cached (L, p) endmembers of the config-seed run of `method` (mvsa / nmf).

    Keyed by the exact normalization (valid_ballots and actual_voters share an
    output folder but not a cache) and by the method's parameters."""
    tag = params_tag(method, method_params(config["unmixing"], method))
    return DISTINCTNESS_CACHE / _norm(config) / year / f"endm_p{p}_seed{_seed(config)}_{tag}.npy"


def load_or_extract(
    Y: np.ndarray, config: configparser.ConfigParser, year: str, p: int, method: str,
    recompute: bool = False,
) -> np.ndarray:
    """The config-seed endmembers of `method` at p, from the cache or computed."""
    path = endmember_cache_path(config, year, p, method)
    if path.exists() and not recompute:
        return np.load(path)
    params = method_params(config["unmixing"], method)
    M = extract_endmembers(Y, p, _seed(config), method, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, M)
    return M


def run_vca(Y: np.ndarray, p: int, seed: int) -> np.ndarray:
    """VCA endmembers (L, p): the picked precincts projected onto VCA's subspace."""
    np.random.seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):  # per-run SNR chatter
        M, *_ = vca(Y, Endmembers=p, verbose="off")
    return M


def load_or_vca(
    Y: np.ndarray, config: configparser.ConfigParser, year: str, p: int,
    recompute: bool = False,
) -> np.ndarray:
    seed = _seed(config)
    path = PROJECTION_CACHE / f"{year}_{_norm(config)}_vca_p{p}_seed{seed}.npy"
    if path.exists() and not recompute:
        return np.load(path)
    M = run_vca(Y, p, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, M)
    return M


def load_or_fit_umap(
    Y: np.ndarray, config: configparser.ConfigParser, year: str, recompute: bool = False
):
    """UMAP fit on all precincts (rows of Y.T), pickled; about 2 min per fit."""
    seed = _seed(config)
    tag = f"nn{UMAP_PARAMS['n_neighbors']}_md{UMAP_PARAMS['min_dist']}"
    path = PROJECTION_CACHE / f"{year}_{_norm(config)}_umap_{tag}_seed{seed}.pkl"
    if path.exists() and not recompute:
        return pickle.loads(path.read_bytes())
    import umap  # bake-time only

    reducer = umap.UMAP(**UMAP_PARAMS, random_state=seed).fit(Y.T)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(reducer))
    return reducer


def density(xy: np.ndarray, bins: int) -> dict:
    """Sparse 2-D histogram of the points `xy` (n, 2) over their bounding box.

    Cells are numbered row-major with the row from y (``idx = row * bins + col``);
    only nonzero cells are kept, their indices delta-encoded (each entry is the
    gap from the previous nonzero cell, the first from 0)."""
    x, y = xy[:, 0], xy[:, 1]
    xe = [float(x.min()), float(x.max())]
    ye = [float(y.min()), float(y.max())]
    H, _, _ = np.histogram2d(y, x, bins=bins, range=[ye, xe])
    flat = H.ravel().astype(np.int64)
    idx = np.flatnonzero(flat)
    return {
        "extent": {"x": xe, "y": ye},
        "idx": np.diff(idx, prepend=0).tolist(),
        "count": flat[idx].tolist(),
    }
