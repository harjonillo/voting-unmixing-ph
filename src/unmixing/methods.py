"""Endmember-extraction methods the pipeline scripts can switch between.

One seed -> endmembers entry point (``extract_endmembers``) shared by
run_pipeline.py, run_sweep.py and the notebook bake scripts, so every script
runs a method with the same config-driven parameters and seeding:

- ``mvsa`` — Minimum Volume Simplex Analysis (VCA init). Seeded through the
  global NumPy RNG (``np.random.seed``), as the scripts always did.
- ``nmf``  — non-negative matrix factorization (notebook 10), W rescaled to the
  data scale (see ``endmember_extraction.nmf``). Seeded through
  ``random_state``.

Abundances are estimated from the endmembers with SUNSAL either way.
"""

from __future__ import annotations

import configparser
import contextlib
import io

import numpy as np

from .endmember_extraction import mvsa, nmf

# method key (CLI / paths / site) -> display label
METHODS = {"mvsa": "MVSA", "nmf": "NMF"}


def method_params(unmix: configparser.SectionProxy, method: str) -> dict:
    """The [unmixing] config parameters of one extraction method.

    NMF keys fall back to notebook 10's settings (with a random init, so the
    seed matters) when a config predates them.
    """
    if method == "mvsa":
        return {"MM_iters": unmix.getint("mvsa_mm_iters")}
    if method == "nmf":
        return {
            "init": unmix.get("nmf_init", "random"),
            "beta_loss": unmix.get("nmf_beta_loss", "kullback-leibler"),
            "solver": unmix.get("nmf_solver", "mu"),
            "max_iter": unmix.getint("nmf_max_iter", 1000),
            "tol": unmix.getfloat("nmf_tol", 1e-4),
        }
    raise ValueError(f"unknown method {method!r}; expected one of {list(METHODS)}")


def params_tag(method: str, params: dict) -> str:
    """Short filename-safe tag pinning a method's parameters (for run caches)."""
    if method == "mvsa":
        return f"mm{params['MM_iters']}"
    return (
        f"nmf-{params['init']}-{params['beta_loss']}-{params['solver']}"
        f"-it{params['max_iter']}-tol{params['tol']:g}"
    )


def extract_endmembers(
    Y: np.ndarray, p: int, seed: int, method: str, params: dict
) -> np.ndarray:
    """(L, p) endmembers of one run of `method` at `seed`.

    Parameters
    ----------
    Y : ndarray, shape (L, N)
        Data: L candidates (rows) x N precincts (columns).
    p : int
        Number of endmembers.
    seed : int
        Run seed (global RNG for MVSA, ``random_state`` for NMF).
    method : str
        A key of ``METHODS``.
    params : dict
        ``method_params(...)`` for that method.
    """
    np.random.seed(seed)
    if method == "mvsa":
        with contextlib.redirect_stdout(io.StringIO()):  # VCA's per-run SNR chatter
            M, *_ = mvsa(Y, p=p, spherize="yes", verbose=0, **params)
        return M
    if method == "nmf":
        M, _ = nmf(Y, p, random_state=seed, **params)
        return M
    raise ValueError(f"unknown method {method!r}; expected one of {list(METHODS)}")
