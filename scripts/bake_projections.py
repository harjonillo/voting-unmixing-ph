"""Bake the precinct cloud and endmembers in 2-D (PCA, UMAP) for the site.

Feeds the Model comparison tab's "Archetypes in the precinct cloud" card, the
site version of notebook 16 (Li & Bioucas-Dias 2008, Fig. 1): per year and
normalization, the precincts projected to two dimensions with the VCA, MVSA and
NMF endmembers at each p overlaid.

PCA and UMAP are fit once per year and normalization, on all precincts, and
shared across p; the endmembers are placed with the fitted projection
(``transform``). The precincts themselves are stored as a sparse ``--bins`` ×
``--bins`` density over each projection's bounding box (src.projection.density),
not as points, so the file stays small whatever the precinct count.

MVSA and NMF endmembers are the config-seed runs cached by
scripts/bake_distinctness.py (run it first; missing ones are computed here and
cached the same way). VCA endmembers and the UMAP fits share notebook 16's cache
(data/notebook_experiments/16_endmember_projections/, gitignored); a first UMAP
fit takes about 2 minutes per year. Needs ``umap-learn`` (``pip install
umap-learn``), which is not in requirements.txt: CI copies the baked files and
never runs this script.

Writes ``data/projections/[<normalization>/]{year}.json`` — small, *committed*
files that scripts/build_static.py copies into site/data/ (one file per
normalization, shared by the MVSA and NMF views)::

    {
      "year": "2025", "normalization": "actual_voters", "seed": 42,
      "ps": [2, ...], "n_precincts": 92486, "bins": 512,
      "methods": ["VCA", "MVSA", "NMF"],
      "pca":  {"explained": [r1, r2], "density": D, "ends": {"<p>": {method: [[x, y], ...]}}},
      "umap": {"density": D, "ends": {...}},
      "min_loading": {"<p>": {method: m}}
    }

with ``D = {"extent": {"x": [min, max], "y": [min, max]}, "idx": [...], "count": [...]}``
(nonzero cells, row-major with the row from y, indices delta-encoded).

Usage::

    python scripts/bake_projections.py                            # config normalization
    python scripts/bake_projections.py --normalization vote_sum   # per-vote runs
    python scripts/bake_projections.py --years 2025 --bins 256
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config, run_subdir, set_normalization
from src.data import load_complete
from src.data.preprocessing import NORMALIZATIONS, preprocess_from_config
from src.projection import density, load_or_extract, load_or_fit_umap, load_or_vca

YEARS = ["2025", "2022", "2019", "2016", "2013"]
# per-ballot runs need a ballot count, which 2013 and 2016 lack (vote_sum only)
PER_BALLOT_YEARS = ["2025", "2022", "2019"]
METHODS = ["VCA", "MVSA", "NMF"]
SIG = 4  # significant digits of the stored coordinates


def year_config(year: str, normalization: str | None):
    """The year's config, with the --normalization override applied."""
    return set_normalization(
        load_config(REPO_ROOT / "configs" / f"config_{year}.ini"), normalization
    )


def rnd(a) -> list:
    """Round an array to SIG significant digits, as nested lists."""
    a = np.asarray(a, dtype=float)
    return np.vectorize(lambda v: float(f"{v:.{SIG}g}"))(a).tolist()


def bake_year(year: str, ps: list[int], bins: int, normalization: str | None,
              recompute: bool) -> dict:
    config = year_config(year, normalization)
    t0 = time.time()
    Y = preprocess_from_config(load_complete(config), config, verbose=False).Y
    ends = {
        p: {
            "VCA": load_or_vca(Y, config, year, p, recompute),
            "MVSA": load_or_extract(Y, config, year, p, "mvsa", recompute),
            "NMF": load_or_extract(Y, config, year, p, "nmf", recompute),
        }
        for p in ps
    }
    pca = PCA(2).fit(Y.T)
    reducer = load_or_fit_umap(Y, config, year, recompute)
    proj = {"pca": (pca.transform(Y.T), pca.transform), "umap": (reducer.embedding_, reducer.transform)}

    out = {
        "year": year,
        "normalization": config["preprocessing"]["normalization"],
        "seed": config["unmixing"].getint("seed"),
        "ps": ps,
        "n_precincts": int(Y.shape[1]),
        "bins": bins,
        "methods": METHODS,
    }
    for name, (cloud, transform) in proj.items():
        out[name] = {
            "density": density(cloud, bins),
            "ends": {str(p): {m: rnd(transform(ends[p][m].T)) for m in METHODS} for p in ps},
        }
    out["pca"] = {"explained": rnd(pca.explained_variance_ratio_), **out["pca"]}
    out["min_loading"] = {
        str(p): {m: float(f"{ends[p][m].min():.{SIG}g}") for m in METHODS} for p in ps
    }
    print(f"{year} ({out['normalization']}): Y {Y.shape}, {time.time() - t0:.0f}s")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", nargs="+", default=None,
                    help="default: every year the normalization has (per ballot: "
                    f"{', '.join(PER_BALLOT_YEARS)}; vote_sum: all)")
    ap.add_argument("--p-min", type=int, default=2)
    ap.add_argument("--p-max", type=int, default=7)
    ap.add_argument("--bins", type=int, default=512, help="density grid per axis")
    ap.add_argument(
        "--normalization",
        choices=list(NORMALIZATIONS),
        default=None,
        help="override [preprocessing] normalization; non-per-ballot runs are "
        "written to a subfolder named after it (src.config.run_subdir)",
    )
    ap.add_argument("--recompute", action="store_true",
                    help="ignore the endmember, VCA and UMAP caches")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data")
    args = ap.parse_args()

    years = args.years or (YEARS if args.normalization == "vote_sum" else PER_BALLOT_YEARS)
    ps = list(range(args.p_min, args.p_max + 1))
    for year in years:
        payload = bake_year(year, ps, args.bins, args.normalization, args.recompute)
        # data/projections/[<normalization>/]{year}.json — method-independent
        out_dir = args.out / "projections" / run_subdir(
            year_config(year, args.normalization), "mvsa"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{year}.json"
        out.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"{year}: wrote {out.relative_to(REPO_ROOT)} ({out.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
