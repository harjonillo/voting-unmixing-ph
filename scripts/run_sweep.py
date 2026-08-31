"""Multi-trial endmember-count sweep.

For each p in [sweep] p_min..p_max, run n_trials MVSA+SUNSAL trials
(different seeds), align archetypes across trials by linear sum assignment (cosine
similarity, reference = lowest-RMSE trial), and write per-p artifacts under
<processed_path>/sweep/p{p}/:

    loadings_mean.csv / loadings_std.csv   consensus loadings (aligned)
    agg_municipality_trials.parquet        per-trial ballot-weighted mean
                                           abundance per municipality
    abundances_ref.parquet                 reference trial, full precinct
                                           resolution (geography + arch cols)
    meta.json                              seeds, rmse_trials, stability, ...

Municipality-level aggregates carry summed ballot weights, so province- and
region-level means can be re-derived exactly (weighted mean of weighted means).

The input CSV and output directory are taken from the per-year config passed
via --config (e.g. configs/config_2025.ini).

Run from the repo root (takes a few minutes; trials run in parallel):
    python scripts/run_sweep.py --config configs/config_2025.ini
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from joblib import Parallel, delayed

from src.config import load_config, processed_path
from src.data import load_complete
from src.data.preprocessing import preprocess_from_config
from src.unmixing import mvsa, sunsal_mod, match_to_reference

MUNI_COLS = ["REGION", "PROVINCE", "CITY_MUNICIPALITY"]
WEIGHT_COL = "information.numberOfValidBallot"

# Grouping columns for each aggregation level the app exposes (a prefix of
# MUNI_COLS). The site build reads the per-level stats written below instead of
# re-deriving them from the per-trial municipality table.
LEVEL_COLS = {
    "region": ["REGION"],
    "province": ["REGION", "PROVINCE"],
    "municipality": ["REGION", "PROVINCE", "CITY_MUNICIPALITY"],
}


def level_stats_from_trials(agg_trials: pd.DataFrame, arch_cols: list[str]) -> pd.DataFrame:
    """Trial mean/std of abundances at each aggregation level and weighting.

    From the per-trial municipality table, re-aggregate to region / province /
    municipality (ballot-weighted and unweighted) per trial — weighted mean =
    sum(arch*w) / sum(w) per (trial, unit) — then take mean and std across
    trials. Vectorized. Returns one long-format frame the site build reads:

        columns: level, weighted, stat, REGION, PROVINCE, CITY_MUNICIPALITY,
                 n_precincts, <WEIGHT_COL>, arch_0 ... arch_{p-1}

    Rows carry only the key columns their level uses (finer ones are NaN);
    ``n_precincts`` is the number of municipalities in the unit and the weight
    column their summed ballots (both trial-invariant).
    """
    frames = []
    for level, gcols in LEVEL_COLS.items():
        base = agg_trials[agg_trials["trial"] == agg_trials["trial"].iloc[0]]
        counts = base.groupby(gcols, observed=True).agg(
            n_precincts=(arch_cols[0], "size"), **{WEIGHT_COL: (WEIGHT_COL, "sum")}
        )
        for weighted in (True, False):
            w = agg_trials[WEIGHT_COL].to_numpy(float) if weighted else np.ones(len(agg_trials))
            work = agg_trials[["trial"] + gcols].copy()
            for c in arch_cols:
                work[c] = agg_trials[c].to_numpy() * w
            work["_w"] = w
            g = work.groupby(["trial"] + gcols, observed=True).sum()
            per_trial = g[arch_cols].div(g["_w"], axis=0).reset_index()
            grouped = per_trial.groupby(gcols, observed=True)[arch_cols]
            for stat, values in (("mean", grouped.mean()), ("std", grouped.std(ddof=1))):
                out = values.join(counts).reset_index()
                out.insert(0, "stat", stat)
                out.insert(0, "weighted", weighted)
                out.insert(0, "level", level)
                frames.append(out)
    return pd.concat(frames, ignore_index=True)


def run_one_trial(Y, p, seed, mvsa_mm_iters, sunsal_al_iters, sunsal_tol):
    np.random.seed(seed)
    M, *_ = mvsa(Y, p=p, MM_iters=mvsa_mm_iters, spherize="yes", verbose=0)
    A, _, _ = sunsal_mod(
        M, Y, positivity="yes", addone="yes",
        AL_iters=sunsal_al_iters, lambda_=0.0, tol=sunsal_tol, verbose="no",
    )
    rmse = float(np.sqrt(np.mean((Y - M @ A) ** 2)))
    return M, A, rmse


def aggregate_to_municipality(A, codes, w, n_units):
    """Ballot-weighted mean abundance per municipality, vectorized.

    A     : (p, N) abundances
    codes : (N,) municipality group code per precinct
    w     : (N,) weights (valid ballots)
    """
    w_sum = np.bincount(codes, weights=w, minlength=n_units)
    out = np.empty((n_units, A.shape[0]))
    for j in range(A.shape[0]):
        out[:, j] = np.bincount(codes, weights=A[j] * w, minlength=n_units) / w_sum
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True,
                        help="per-year config, e.g. configs/config_2025.ini")
    parser.add_argument("--n-trials", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    sweep = config["sweep"]
    unmix = config["unmixing"]
    p_range = range(sweep.getint("p_min"), sweep.getint("p_max") + 1)
    n_trials = args.n_trials or sweep.getint("n_trials")
    base_seed = sweep.getint("base_seed")
    n_jobs = sweep.getint("n_jobs")

    print("== loading ==")
    df = load_complete(config)
    pre = preprocess_from_config(df, config)
    Y = pre.Y

    # municipality grouping, shared by all trials
    muni_index = pd.MultiIndex.from_frame(pre.df_geo[MUNI_COLS])
    codes, uniques = pd.factorize(muni_index)
    w = pre.df_geo[WEIGHT_COL].to_numpy(dtype=float)
    muni_table = pd.DataFrame(list(uniques), columns=MUNI_COLS)
    muni_table["n_precincts"] = np.bincount(codes)
    muni_table[WEIGHT_COL] = np.bincount(codes, weights=w)
    n_units = len(muni_table)
    print(f"{n_units} municipalities")

    sweep_root = processed_path(config, "sweep")

    for p in p_range:
        t0 = time.time()
        print(f"\n== p = {p}: {n_trials} trials (n_jobs={n_jobs}) ==")
        results = Parallel(n_jobs=n_jobs)(
            delayed(run_one_trial)(
                Y, p, base_seed + t,
                unmix.getint("mvsa_mm_iters"),
                unmix.getint("sunsal_al_iters"),
                unmix.getfloat("sunsal_tol"),
            )
            for t in range(n_trials)
        )
        rmse_trials = np.array([r[2] for r in results])
        ref = int(np.argmin(rmse_trials))
        M_ref = results[ref][0]

        # Align every trial to the lowest-RMSE trial by linear sum assignment on cosine similarity
        M_aligned = np.empty((n_trials, Y.shape[0], p))
        A_aligned = [None] * n_trials
        sims = np.empty((n_trials, p))
        for t, (M, A, _) in enumerate(results):
            perm, sim = match_to_reference(M_ref, M)
            M_aligned[t] = M[:, perm]
            A_aligned[t] = A[perm, :]
            sims[t] = sim

        loadings_mean = M_aligned.mean(axis=0)
        loadings_std = M_aligned.std(axis=0, ddof=1)
        stability = sims.mean(axis=0)          # per-archetype mean cosine to ref

        # per-trial municipality aggregates (long format)
        agg_frames = []
        for t in range(n_trials):
            vals = aggregate_to_municipality(A_aligned[t], codes, w, n_units)
            frame = muni_table.copy()
            frame["trial"] = t
            for j in range(p):
                frame[f"arch_{j}"] = vals[:, j]
            agg_frames.append(frame)
        agg_trials = pd.concat(agg_frames, ignore_index=True)

        # reference trial at full precinct resolution
        df_ref = pre.df_geo.reset_index(drop=True).copy()
        for j in range(p):
            df_ref[f"arch_{j}"] = A_aligned[ref][j, :]

        out = sweep_root / f"p{p}"
        out.mkdir(parents=True, exist_ok=True)
        arch_cols = [f"arch_{j}" for j in range(p)]
        pd.DataFrame(
            loadings_mean, 
            index=pre.candidate_labels, 
            columns=arch_cols
        ).rename_axis("candidate").to_csv(out / "loadings_mean.csv")
        pd.DataFrame(
            loadings_std, 
            index=pre.candidate_labels, 
            columns=arch_cols
        ).rename_axis("candidate").to_csv(out / "loadings_std.csv")
        agg_trials.to_parquet(out / "agg_municipality_trials.parquet", index=False)
        # Per-level trial mean/std the site build serializes (so build_static.py
        # reads these instead of re-aggregating the trials itself).
        level_stats_from_trials(agg_trials, arch_cols).to_parquet(
            out / "level_stats.parquet", index=False
        )
        df_ref.to_parquet(out / "abundances_ref.parquet", index=False)
        with open(out / "meta.json", "w") as f:
            json.dump({
                "p": p,
                "n_trials": n_trials,
                "base_seed": base_seed,
                "reference_trial": ref,
                "rmse_trials": rmse_trials.tolist(),
                "rmse_mean": float(rmse_trials.mean()),
                "rmse_std": float(rmse_trials.std(ddof=1)),
                "stability_per_archetype": stability.tolist(),
                "stability_mean": float(stability.mean()),
                "preprocessing": pre.params,
                "candidate_labels": pre.candidate_labels,
            }, f, indent=2)

        print(f"p={p}: RMSE {rmse_trials.mean():.5f} ± {rmse_trials.std(ddof=1):.5f}, "
              f"stability {stability.mean():.4f} "
              f"(min per-archetype {stability.min():.4f})  [{time.time() - t0:.0f}s]")

    print(f"\nwrote {sweep_root}/p{{{p_range.start}..{p_range.stop - 1}}}/")


if __name__ == "__main__":
    main()
