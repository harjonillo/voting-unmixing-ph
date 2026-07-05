"""End-to-end unmixing pipeline.

load complete CSV -> filter/normalize -> noise + HySime -> MVSA -> SUNSAL
-> write data/processed/{endmembers.csv, abundances.parquet, meta.json}

Run from the repo root:
    python scripts/run_pipeline.py [--config configs/config.ini] [--n-archetypes 7]
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.data import load_complete
from src.data.loading import save_processed
from src.data.preprocessing import preprocess_from_config
from src.unmixing import est_noise, hysime, mvsa, sunsal_mod


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--n-archetypes", type=int, default=None,
                        help="override [unmixing] n_archetypes (0 = use HySime kf)")
    args = parser.parse_args()

    config = load_config(args.config)
    unmix = config["unmixing"]
    seed = unmix.getint("seed")
    np.random.seed(seed)

    print("== loading ==")
    df = load_complete(config)
    pre = preprocess_from_config(df, config)
    Y = pre.Y

    print("\n== noise / HySime ==")
    w_hat, Rw_hat = est_noise(Y, noise_type="additive", verbose=False)
    kf, *_ = hysime(Y, w_hat, Rw_hat, verbose=False)
    print(f"HySime signal subspace dimension kf = {kf}")

    n_archetypes = args.n_archetypes if args.n_archetypes is not None else unmix.getint("n_archetypes")
    if n_archetypes == 0:
        n_archetypes = kf
    print(f"n_archetypes = {n_archetypes}")

    print("\n== MVSA ==")
    t0 = time.time()
    endmembers, *_ = mvsa(
        Y, p=n_archetypes,
        MM_iters=unmix.getint("mvsa_mm_iters"),
        spherize="yes", verbose=0,
    )
    print(f"M: {endmembers.shape}  ({time.time() - t0:.1f}s)")

    print("\n== SUNSAL ==")
    t0 = time.time()
    abundances, res_p, res_d = sunsal_mod(
        endmembers, Y,
        positivity="yes", addone="yes",
        AL_iters=unmix.getint("sunsal_al_iters"),
        lambda_=0.0, tol=unmix.getfloat("sunsal_tol"),
        verbose="no",
    )
    print(f"S: {abundances.shape}  ({time.time() - t0:.1f}s)")

    rmse = float(np.sqrt(np.mean((Y - endmembers @ abundances) ** 2)))
    sum_dev = np.abs(abundances.sum(axis=0) - 1.0)
    print(f"reconstruction RMSE = {rmse:.6f}")
    print(f"|sum(abundances)-1|: mean {sum_dev.mean():.2e}, max {sum_dev.max():.2e}")

    meta = {
        "preprocessing": pre.params,
        "hysime_kf": int(kf),
        "n_archetypes": int(n_archetypes),
        "seed": seed,
        "rmse": rmse,
        "candidate_labels": pre.candidate_labels,
    }
    out = save_processed(pre, endmembers, abundances, meta, config)
    print(f"\nwrote {out}/endmembers.csv, abundances.parquet, meta.json")


if __name__ == "__main__":
    main()
