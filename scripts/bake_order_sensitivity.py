"""Notebook 09 (randomizing precinct order) as a script, run across election years.

For each year (``configs/config_{year}.ini``) and each archetype count p in
``--ps`` (notebook 09's 2..6 by default), rerun notebook 09's design against a
**reference run** (canonical precinct order, the config's pipeline seed):

- **Arm A — determinism check:** canonical order, same seed, rerun
  ``--arm-a-trials`` times; every rerun should be bitwise identical to the
  reference. (Notebook 09 reran it once per trial; it was always identical, so a
  couple of reruns suffice here.)
- **Arm B — order sensitivity:** shuffled precinct order
  (``randomize_precinct_order=True``, shuffle seed ``--perm-seed`` + trial), same
  pipeline seed. Candidate order is untouched by the shuffle.
- **Arm C — seed sensitivity (the yardstick):** canonical order, pipeline seed
  ``seed + 1 + trial``.

Each trial's archetypes are Hungarian-matched to the reference under each metric
(``src.unmixing.matching``), and the matched similarities are pooled over
archetypes × trials per (p, arm, metric) — the samples behind notebook 09's
boxplots, baked raw so the site can draw the same boxes (quartiles, 1.5 × IQR
whiskers, outliers).

Only the endmembers enter the summary, so each run is seed → MVSA: est_noise and
HySime don't touch the RNG and only matter when p is left to HySime, and SUNSAL
(abundances) runs after MVSA, so dropping them leaves the endmembers bitwise
unchanged. Notebook 09's abundance-consistency views (per-archetype Pearson r,
per-precinct |Δ abundance|) are therefore not reproduced. Each shuffled vote
matrix is checked to be an exact column permutation of the reference one, then
rebuilt from that permutation on demand instead of being held in memory.

Runs go in parallel (``[sweep] n_jobs`` of that year's config unless
``--n-jobs``); endmembers are cached as ``.npz`` under
``data/notebook_experiments/09_precinct_order/{year}/`` (gitignored); delete a
file or pass ``--recompute`` to rerun.

Writes ``data/order_sensitivity/{year}.json`` — small, *committed* files that
scripts/build_static.py copies into site/data/::

    {
      "year": "2025", "ps": [2, ...], "n_trials": 50, "arm_a_trials": 2,
      "seed": 42, "perm_seed": 1000,
      "deterministic": [true, ...],          # Arm A bitwise == reference, per p
      "arms": {"B": "shuffled precinct order", "C": "varying seed"},
      "metrics": ["cos12", "cos", "spearman", "wtau", "rbo", "jac12"],
      "sims": {arm: {metric: [[matched similarities, trials × archetypes]
                              per p]}}
    }

Metric keys match lineage/{year}.json's "sims" and distinctness/{year}.json, so
the site's one "Similarity metric" selector drives every compare-tab chart.

Run from the repo root (several minutes per year), before build_static.py:
    python scripts/bake_order_sensitivity.py                    # all years
    python scripts/bake_order_sensitivity.py --years 2025 --trials 10
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
import pandas as pd
from joblib import Parallel, delayed

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config
from src.data import load_complete
from src.data.preprocessing import preprocess_from_config
from src.unmixing import mvsa
from src.unmixing.matching import match_to_reference

YEARS = ["2025", "2022", "2019", "2016", "2013"]
CACHE_DIR = REPO_ROOT / "data" / "notebook_experiments" / "09_precinct_order"

# site short name -> src.unmixing.matching registered name (same keys as the
# lineage JSON's "sims" and the distinctness JSON, so one selector drives every
# compare-tab chart).
METRICS = {
    "cos12": "top12_cosine",
    "cos": "cosine",
    "spearman": "spearman",
    "wtau": "weighted_tau",
    "rbo": "rbo",
    "jac12": "top12_jaccard",
}
ARMS = {"B": "shuffled precinct order", "C": "varying seed"}
ROUND = 4


def endmembers(Y: np.ndarray, p: int, seed: int, mm_iters: int) -> np.ndarray:
    """(L, p) MVSA endmembers — the notebooks' run_pipeline(...)['endm']."""
    np.random.seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):  # VCA's per-run SNR chatter
        M, *_ = mvsa(Y, p=p, MM_iters=mm_iters, spherize="yes", verbose=0)
    return M


def shuffle_permutations(df, config, Y_ref, pre_ref, n_trials, perm_seed):
    """Per-trial column permutations reproducing notebook 09's shuffled inputs.

    Trial t's preprocessing (shuffle RNG seeded with perm_seed + t) yields
    exactly ``Y_ref[:, pos]`` — preprocessing normalizes each precinct on its
    own — which is asserted, so only ``pos`` needs keeping.
    """
    ref_ids = pd.Index(pre_ref.params["precinct_ids"])
    perms = []
    for t in range(n_trials):
        np.random.seed(perm_seed + t)  # drives only the precinct shuffle
        pre = preprocess_from_config(
            df, config, randomize_precinct_order=True, verbose=False
        )
        assert pre.ranked_columns == pre_ref.ranked_columns  # candidates untouched
        pos = ref_ids.get_indexer(pre.params["precinct_ids"])
        assert (pos >= 0).all() and len(np.unique(pos)) == Y_ref.shape[1]
        assert np.array_equal(pre.Y, Y_ref[:, pos])
        perms.append(pos)
    return perms


def shuffled(Y_ref: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Y_ref with columns reordered by pos, in Y_ref's memory layout."""
    return np.array(Y_ref[:, pos], order="F" if Y_ref.flags.f_contiguous else "C")


def run_experiment(Y_ref, perms, p, seed, mm_iters, n_trials, arm_a, n_jobs):
    """Reference + arms A/B/C endmembers at one p, all runs in parallel."""
    jobs = (
        [delayed(endmembers)(Y_ref, p, seed, mm_iters) for _ in range(1 + arm_a)]
        + [
            delayed(endmembers)(shuffled(Y_ref, pos), p, seed, mm_iters)
            for pos in perms
        ]
        + [
            delayed(endmembers)(Y_ref, p, seed + 1 + t, mm_iters)
            for t in range(n_trials)
        ]
    )
    mats = Parallel(n_jobs=n_jobs)(jobs)
    return {
        "ref": mats[0],
        "A": np.stack(mats[1 : 1 + arm_a]) if arm_a else np.empty((0,)),
        "B": np.stack(mats[1 + arm_a : 1 + arm_a + n_trials]),
        "C": np.stack(mats[1 + arm_a + n_trials :]),
    }


def bake_year(year, ps, n_trials, arm_a, perm_seed, n_jobs, recompute) -> dict:
    config = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
    seed = config["unmixing"].getint("seed")
    mm_iters = config["unmixing"].getint("mvsa_mm_iters")
    n_jobs = n_jobs or config["sweep"].getint("n_jobs")

    cache = CACHE_DIR / year
    cache.mkdir(parents=True, exist_ok=True)
    path = {
        p: cache / f"endm_p{p}_seed{seed}_permseed{perm_seed}_trials{n_trials}"
        f"_a{arm_a}_mm{mm_iters}.npz"
        for p in ps
    }
    todo = [p for p in ps if recompute or not path[p].exists()]

    if todo:
        df = load_complete(config)
        pre_ref = preprocess_from_config(df, config, verbose=False)
        Y_ref = pre_ref.Y
        print(f"{year}: Y {Y_ref.shape}; preparing {n_trials} precinct shuffles")
        perms = shuffle_permutations(df, config, Y_ref, pre_ref, n_trials, perm_seed)
        del df
        for p in todo:
            t0 = time.time()
            e = run_experiment(
                Y_ref, perms, p, seed, mm_iters, n_trials, arm_a, n_jobs
            )
            np.savez(path[p], **e)
            print(
                f"{year} p={p}: {1 + arm_a + 2 * n_trials} runs in "
                f"{time.time() - t0:.0f}s (n_jobs={n_jobs})"
            )
    else:
        print(f"{year}: all p cached")

    deterministic = []
    sims = {arm: {m: [] for m in METRICS} for arm in ARMS}
    for p in ps:
        e = np.load(path[p])
        ref = e["ref"]
        deterministic.append(all(np.array_equal(ref, M) for M in e["A"]))
        for arm in ARMS:
            for short, name in METRICS.items():
                pooled = np.concatenate(
                    [match_to_reference(ref, M, name)[1] for M in e[arm]]
                )
                sims[arm][short].append([round(float(s), ROUND) for s in pooled])
    if arm_a and not all(deterministic):
        bad = [p for p, ok in zip(ps, deterministic) if not ok]
        print(f"{year}: WARNING — Arm A reruns differ from the reference at p={bad}")

    return {
        "year": year,
        "ps": ps,
        "n_trials": n_trials,
        "arm_a_trials": arm_a,
        "seed": seed,
        "perm_seed": perm_seed,
        "deterministic": deterministic,
        "arms": ARMS,
        "metrics": list(METRICS),
        "sims": sims,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="+", default=YEARS)
    ap.add_argument("--ps", nargs="+", type=int, default=[2, 3, 4, 5, 6])
    ap.add_argument("--trials", type=int, default=50, help="trials per arm B / C")
    ap.add_argument(
        "--arm-a-trials", type=int, default=2, help="determinism reruns (Arm A)"
    )
    ap.add_argument(
        "--perm-seed", type=int, default=1000, help="shuffle seed stream (PERM_SEED)"
    )
    ap.add_argument(
        "--n-jobs", type=int, default=None, help="default: the config's [sweep] n_jobs"
    )
    ap.add_argument("--recompute", action="store_true", help="ignore the run cache")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data")
    args = ap.parse_args()

    out_dir = args.out / "order_sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in args.years:
        payload = bake_year(
            year,
            sorted(args.ps),
            args.trials,
            args.arm_a_trials,
            args.perm_seed,
            args.n_jobs,
            args.recompute,
        )
        out = out_dir / f"{year}.json"
        out.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"{year}: wrote {out} ({out.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
