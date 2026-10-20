"""Deterministic (NNDSVD-initialized) NMF run per p, next to the NMF sweep.

The NMF sweep (``run_sweep.py --method nmf``) varies a random initialization
across trials. NNDSVD initializes from the data's SVD instead, so there is a
single seed-independent result per p; this script computes it for every p the
NMF sweep has and aligns its archetypes to the sweep's consensus loadings
(Hungarian match on cosine similarity to loadings_mean.csv), so archetype k
means the same thing in both. Writes, under <processed_path>/nmf/sweep/p{p}/:

    nndsvd_loadings.csv   (L, p) loadings, columns aligned to loadings_mean
    nndsvd_meta.json      init, method params, RMSE (vs the random trials'),
                          per-archetype matched cosine, fraction of zero
                          loadings

All other NMF parameters come from the config's [unmixing] nmf_* keys, as for
the sweep; only the initialization differs. With the "mu" solver, NNDSVD's
exact zeros stay zero (sklearn warns about it); ``zero_fraction`` records how
many there are. ``--init nndsvda`` fills them with the data mean instead.

Requires the NMF sweep. Run from the repo root (seconds to minutes per year):
    python scripts/run_nndsvd.py --config configs/config_2025.ini
"""

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, method_path
from src.data import load_complete
from src.data.loading import load_sweep
from src.data.preprocessing import preprocess_from_config
from src.unmixing import extract_endmembers, match_to_reference, method_params, sunsal_mod


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", required=True, help="per-year config, e.g. configs/config_2025.ini"
    )
    parser.add_argument(
        "--init",
        choices=["nndsvd", "nndsvda"],
        default="nndsvd",
        help="deterministic NMF initialization (default: nndsvd)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    unmix = config["unmixing"]
    params = {**method_params(unmix, "nmf"), "init": args.init}

    sweep = load_sweep(config, method="nmf")
    if not sweep:
        sys.exit(
            f"No NMF sweep under {method_path(config, 'nmf', 'sweep')}; run "
            f"`python scripts/run_sweep.py --config {args.config} --method nmf` first."
        )

    print("== loading ==")
    df = load_complete(config)
    pre = preprocess_from_config(df, config)
    Y = pre.Y

    for p, entry in sweep.items():
        t0 = time.time()
        lm = entry["loadings_mean"]
        if list(lm.index) != pre.candidate_labels:
            sys.exit(f"p={p}: sweep candidates differ from the preprocessed data")

        with warnings.catch_warnings():
            # mu can't update NNDSVD's zeros; recorded as zero_fraction instead
            warnings.filterwarnings("ignore", message="The multiplicative update")
            M = extract_endmembers(Y, p, 0, "nmf", params)  # seed unused by NNDSVD
        A, _, _ = sunsal_mod(
            M,
            Y,
            positivity="yes",
            addone="yes",
            AL_iters=unmix.getint("sunsal_al_iters"),
            lambda_=0.0,
            tol=unmix.getfloat("sunsal_tol"),
            verbose="no",
        )
        rmse = float(np.sqrt(np.mean((Y - M @ A) ** 2)))
        perm, sim = match_to_reference(lm.to_numpy(), M)
        M = M[:, perm]

        out = method_path(config, "nmf", "sweep", f"p{p}")
        pd.DataFrame(M, index=lm.index, columns=lm.columns).rename_axis(
            "candidate"
        ).to_csv(out / "nndsvd_loadings.csv")
        rmse_trials = entry["meta"]["rmse_trials"]
        with open(out / "nndsvd_meta.json", "w") as f:
            json.dump(
                {
                    "p": p,
                    "init": args.init,
                    "method_params": params,
                    "rmse": rmse,
                    # share of the random-init trials this run beats on RMSE
                    "rmse_rank_frac": float(np.mean(np.array(rmse_trials) > rmse)),
                    "matched_cosine_to_sweep_mean": sim.tolist(),
                    "zero_fraction": float(np.mean(M == 0)),
                },
                f,
                indent=2,
            )
        print(
            f"p={p}: RMSE {rmse:.5f} (random {entry['meta']['rmse_mean']:.5f} ± "
            f"{entry['meta']['rmse_std']:.5f}), cosine to sweep mean "
            f"{np.round(sim, 3).tolist()}, zeros {np.mean(M == 0):.1%}  "
            f"[{time.time() - t0:.0f}s]"
        )

    print(f"\nwrote {method_path(config, 'nmf', 'sweep')}/p*/nndsvd_*")


if __name__ == "__main__":
    main()
