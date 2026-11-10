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

Each p also gets the reconstruction **RMSE** of that same run: SUNSAL
abundances (positivity + sum-to-one, the config's ``sunsal_al_iters`` /
``sunsal_tol``, as in scripts/run_sweep.py) and
``sqrt(mean((Y - M A)**2))`` over every candidate × precinct entry, in the
normalization's units (votes/ballot or votes/vote). It is one run at the config
seed, so at p ≤ 7 it is comparable to, not equal to, the sweep's trial mean.

Metrics (notebook 08's sweep set, implementations from ``src.unmixing.matching``):
cosine on the top-12 union, full cosine, Spearman ρ, weighted Kendall τ, RBO and
top-12 Jaccard. Signed [-1, 1] similarities map to distance as (1 − s) / 2,
unsigned [0, 1] ones as 1 − s (notebook 08's ``to_distance``).

``--method nmf`` runs the same sweep with NMF endmembers (notebook 10; the
config's ``nmf_*`` parameters, seeded through ``random_state``) instead of MVSA.

Only the endmembers enter the metric, so each run is seed → MVSA: est_noise and
HySime don't touch the RNG and only matter when p is left to HySime, and SUNSAL
(abundances) runs after MVSA, so dropping them leaves the endmembers bitwise
unchanged. Runs within a year go in parallel (``[sweep] n_jobs`` of that year's
config unless ``--n-jobs``) and are cached as ``.npy`` under
``data/notebook_experiments/08_distinctness/{year}/`` (gitignored); delete a file
or pass ``--recompute`` to rerun. RMSEs are cached next to them
(``rmse_p{p}_seed{seed}_{tag}_al{iters}_tol{tol}.json``), so adding RMSE to an
existing bake reuses the cached endmembers and only runs SUNSAL.

Writes ``data/distinctness/{year}.json`` (NMF: ``data/distinctness/nmf/{year}.json``)
— small, *committed* files that scripts/build_static.py copies into site/data/::

    {
      "year": "2025", "method": "mvsa", "seed": 42, "ps": [2, ...],
      "metrics": ["cos12", "cos", "spearman", "wtau", "rbo", "jac12"],
      "distinct": {"<p>": {metric: {"min": d, "mean": d}}},
      "rmse": {"<p>": rmse}
    }

Metric keys match lineage/{year}.json's "sims" and order_sensitivity/{year}.json,
so the site's one "Similarity metric" selector drives every compare-tab chart.

Run from the repo root (a few minutes per year), before build_static.py:
    python scripts/bake_distinctness.py                    # all years
    python scripts/bake_distinctness.py --years 2025 2022  # a subset
    python scripts/bake_distinctness.py --method nmf       # NMF endmembers
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config, run_subdir, set_normalization
from src.data import load_complete
from src.data.preprocessing import NORMALIZATIONS, preprocess_from_config
from src.unmixing import METHODS, extract_endmembers, method_params, sunsal_mod
from src.unmixing.methods import params_tag
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


def reconstruction_rmse(Y: np.ndarray, M: np.ndarray, al_iters: int, tol: float) -> float:
    """RMSE of Y ≈ M A with SUNSAL abundances, as in scripts/run_sweep.py."""
    A, _, _ = sunsal_mod(
        M, Y, positivity="yes", addone="yes", AL_iters=al_iters, lambda_=0.0,
        tol=tol, verbose="no",
    )
    return float(np.sqrt(np.mean((Y - M @ A) ** 2)))


def year_config(year: str, normalization: str | None):
    """The year's config, with the --normalization override applied."""
    return set_normalization(
        load_config(REPO_ROOT / "configs" / f"config_{year}.ini"), normalization
    )


def bake_year(
    year: str,
    ps: list[int],
    method: str,
    n_jobs: int | None,
    recompute: bool,
    normalization: str | None = None,
) -> dict:
    config = year_config(year, normalization)
    seed = config["unmixing"].getint("seed")
    params = method_params(config["unmixing"], method)
    n_jobs = n_jobs or config["sweep"].getint("n_jobs")

    # cache keyed by the exact normalization (params_tag covers the method):
    # valid_ballots and actual_voters share an output folder but not a cache
    cache = CACHE_DIR / config["preprocessing"]["normalization"] / year
    cache.mkdir(parents=True, exist_ok=True)
    tag = params_tag(method, params)
    path = {p: cache / f"endm_p{p}_seed{seed}_{tag}.npy" for p in ps}
    todo = [p for p in ps if recompute or not path[p].exists()]
    al_iters = config["unmixing"].getint("sunsal_al_iters")
    tol = config["unmixing"].getfloat("sunsal_tol")
    rmse_path = {
        p: cache / f"rmse_p{p}_seed{seed}_{tag}_al{al_iters}_tol{tol:g}.json" for p in ps
    }
    rmse_todo = [p for p in ps if p in todo or not rmse_path[p].exists()]

    Y = None
    if todo or rmse_todo:
        Y = preprocess_from_config(load_complete(config), config, verbose=False).Y

    if todo:
        print(
            f"{year}: Y {Y.shape}, running {METHODS[method]} p={todo} (n_jobs={n_jobs})"
        )
        t0 = time.time()
        # largest p first: the slowest runs start early, so workers finish together
        order = sorted(todo, reverse=True)
        mats = Parallel(n_jobs=n_jobs)(
            delayed(extract_endmembers)(Y, p, seed, method, params) for p in order
        )
        for p, M in zip(order, mats):
            np.save(path[p], M)
        print(f"{year}: done in {time.time() - t0:.0f}s")
    else:
        print(f"{year}: all p cached")

    if rmse_todo:
        print(f"{year}: SUNSAL for RMSE at p={rmse_todo} (n_jobs={n_jobs})")
        t0 = time.time()
        order = sorted(rmse_todo, reverse=True)
        rmses = Parallel(n_jobs=n_jobs)(
            delayed(reconstruction_rmse)(Y, np.load(path[p]), al_iters, tol) for p in order
        )
        for p, r in zip(order, rmses):
            rmse_path[p].write_text(json.dumps({"rmse": r}))
        print(f"{year}: RMSE done in {time.time() - t0:.0f}s")

    return {
        "year": year,
        "method": method,
        "normalization": config["preprocessing"]["normalization"],
        "seed": seed,
        "ps": ps,
        "metrics": list(METRICS),
        "distinct": {str(p): distinctness(np.load(path[p])) for p in ps},
        # one run at the config seed; normalization's units (votes/ballot or votes/vote)
        "rmse": {str(p): json.loads(rmse_path[p].read_text())["rmse"] for p in ps},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="+", default=YEARS)
    ap.add_argument("--p-min", type=int, default=2)
    ap.add_argument("--p-max", type=int, default=12)
    ap.add_argument(
        "--method",
        choices=list(METHODS),
        default="mvsa",
        help="endmember extraction method (default: mvsa)",
    )
    ap.add_argument(
        "--n-jobs", type=int, default=None, help="default: the config's [sweep] n_jobs"
    )
    ap.add_argument(
        "--normalization",
        choices=list(NORMALIZATIONS),
        default=None,
        help="override [preprocessing] normalization; non-per-ballot runs are "
        "written to a subfolder named after it (src.config.run_subdir)",
    )
    ap.add_argument("--recompute", action="store_true", help="ignore the run cache")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data")
    args = ap.parse_args()

    ps = list(range(args.p_min, args.p_max + 1))
    for year in args.years:
        payload = bake_year(
            year, ps, args.method, args.n_jobs, args.recompute, args.normalization
        )
        # data/distinctness/[<normalization>/][<method>/]{year}.json
        out_dir = args.out / "distinctness" / run_subdir(
            year_config(year, args.normalization), args.method
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{year}.json"
        out.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"{year}: wrote {out} ({out.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
