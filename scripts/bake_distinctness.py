"""Notebook 08 (archetype uniqueness) as a script, run across election years.

For each year (``configs/config_{year}.ini``) and each archetype count p in
``--p-min``..``--p-max`` (notebook 08's 2..12 by default), run the unmixing once
at the config's pipeline seed — notebook 08's ``run_pipeline(Y, p, seed=SEED)``
sweep — then map the p×p similarity matrix between the archetypes' loading
columns onto a common 0 = identical … 1 = maximally distinct scale and collapse
it to two scalars per metric:

- **min** off-diagonal distance — the most-overlapping pair. Decreases towards a
  floor as p grows; past it, each added archetype mostly duplicates an existing
  one.
- **mean** off-diagonal distance — overall spread.

Metrics (notebook 08's sweep set, implementations from ``src.unmixing.matching``):
cosine on the top-12 union, full cosine, Spearman ρ, weighted Kendall τ, RBO and
top-12 Jaccard. Signed [-1, 1] similarities map to distance as (1 − s) / 2,
unsigned [0, 1] ones as 1 − s (notebook 08's ``to_distance``).

Only the endmembers enter the metric, so each run is seed → MVSA: est_noise and
HySime don't touch the RNG and only matter when p is left to HySime, and SUNSAL
(abundances) runs after MVSA, so dropping them leaves the endmembers bitwise
unchanged. Runs within a year go in parallel (``[sweep] n_jobs`` of that year's
config unless ``--n-jobs``) and are cached as ``.npy`` under
``data/notebook_experiments/08_distinctness/{year}/`` (gitignored); delete a file
or pass ``--recompute`` to rerun.

Writes ``data/distinctness/{year}.json`` — small, *committed* files that
scripts/build_static.py copies into site/data/::

    {
      "year": "2025", "seed": 42, "ps": [2, ...],
      "metrics": ["cos12", "cos", "spearman", "wtau", "rbo", "jac12"],
      "distinct": {"<p>": {metric: {"min": d, "mean": d}}}
    }

Metric keys match lineage/{year}.json's "sims" and order_sensitivity/{year}.json,
so the site's one "Similarity metric" selector drives every compare-tab chart.

Run from the repo root (a few minutes per year), before build_static.py:
    python scripts/bake_distinctness.py                    # all years
    python scripts/bake_distinctness.py --years 2025 2022  # a subset
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config
from src.data import load_complete
from src.data.preprocessing import preprocess_from_config
from src.unmixing import mvsa
from src.unmixing.matching import similarity_matrix

YEARS = ["2025", "2022", "2019", "2016", "2013"]
CACHE_DIR = REPO_ROOT / "data" / "notebook_experiments" / "08_distinctness"

# site short name -> (src.unmixing.matching registered name, signed?)
METRICS = {
    "cos12": ("top12_cosine", True),
    "cos": ("cosine", True),
    "spearman": ("spearman", True),
    "wtau": ("weighted_tau", True),
    "rbo": ("rbo", False),
    "jac12": ("top12_jaccard", False),
}
ROUND = 3


def endmembers(Y: np.ndarray, p: int, seed: int, mm_iters: int) -> np.ndarray:
    """(L, p) MVSA endmembers — the notebooks' run_pipeline(...)['endm']."""
    np.random.seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):  # VCA's per-run SNR chatter
        M, *_ = mvsa(Y, p=p, MM_iters=mm_iters, spherize="yes", verbose=0)
    return M


def to_distance(S: np.ndarray, signed: bool) -> np.ndarray:
    """Similarity matrix -> 0 (identical) … 1 (maximally distinct) distance."""
    return (1.0 - S) / 2.0 if signed else 1.0 - S


def distinctness(E: np.ndarray) -> dict:
    """Min / mean off-diagonal distance of one (L, p) loading matrix, per metric."""
    p = E.shape[1]
    out = {}
    for short, (name, signed) in METRICS.items():
        D = to_distance(similarity_matrix(E, E, name), signed)
        off = D[np.triu_indices(p, 1)]
        out[short] = {
            "min": round(float(off.min()), ROUND),
            "mean": round(float(off.mean()), ROUND),
        }
    return out


def bake_year(
    year: str, ps: list[int], n_jobs: int | None, recompute: bool
) -> dict:
    config = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
    seed = config["unmixing"].getint("seed")
    mm_iters = config["unmixing"].getint("mvsa_mm_iters")
    n_jobs = n_jobs or config["sweep"].getint("n_jobs")

    cache = CACHE_DIR / year
    cache.mkdir(parents=True, exist_ok=True)
    path = {p: cache / f"endm_p{p}_seed{seed}_mm{mm_iters}.npy" for p in ps}
    todo = [p for p in ps if recompute or not path[p].exists()]

    if todo:
        Y = preprocess_from_config(load_complete(config), config, verbose=False).Y
        print(f"{year}: Y {Y.shape}, running p={todo} (n_jobs={n_jobs})")
        t0 = time.time()
        # largest p first: the slowest runs start early, so workers finish together
        order = sorted(todo, reverse=True)
        mats = Parallel(n_jobs=n_jobs)(
            delayed(endmembers)(Y, p, seed, mm_iters) for p in order
        )
        for p, M in zip(order, mats):
            np.save(path[p], M)
        print(f"{year}: done in {time.time() - t0:.0f}s")
    else:
        print(f"{year}: all p cached")

    return {
        "year": year,
        "seed": seed,
        "ps": ps,
        "metrics": list(METRICS),
        "distinct": {str(p): distinctness(np.load(path[p])) for p in ps},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="+", default=YEARS)
    ap.add_argument("--p-min", type=int, default=2)
    ap.add_argument("--p-max", type=int, default=12)
    ap.add_argument(
        "--n-jobs", type=int, default=None, help="default: the config's [sweep] n_jobs"
    )
    ap.add_argument("--recompute", action="store_true", help="ignore the run cache")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data")
    args = ap.parse_args()

    ps = list(range(args.p_min, args.p_max + 1))
    out_dir = args.out / "distinctness"
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in args.years:
        payload = bake_year(year, ps, args.n_jobs, args.recompute)
        out = out_dir / f"{year}.json"
        out.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"{year}: wrote {out} ({out.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
