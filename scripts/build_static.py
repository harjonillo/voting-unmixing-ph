"""Bake the voting-archetype explorer into a fully static dataset.

The Streamlit app does no on-demand computation beyond cheap pandas
aggregation, argmax, a tiny Hungarian match, a geo-join and Plotly rendering
(see the migration plan). The user's input space is small and enumerable, so
this script pre-computes every combination offline and writes plain JSON +
simplified GeoJSON. A static front-end (FastHTML shell + Plotly.js) then only
loads a file and draws — no Pyodide, no scientific stack in the browser.

What it writes under ``--out`` (default ``site/data``)::

    manifest.json                      years, levels, per-year archetype counts,
                                       candidate labels, colors, sweep p-values.
    geo/province.geojson               province polygons, id = PROV_KEY (shared).
    geo/municipality.geojson           municipal polygons pooled across years,
                                       id = "PROV_KEY::CITY_MUNICIPALITY" (shared).
    geo/{year}_region.geojson          regions dissolved by that year's
                                       province->region map, id = REGION.
    values/{year}_{level}_{w|u}.json   one record per unit: arch_* means,
                                       dominant (post-join), turnout, counts.
    loadings/{year}.json               endmember loadings (mean) + sweep-trial std.
    sweep/{year}_p{p}.json             per-p loadings mean/std + level stats
                                       (trial mean/std) for the comparison tab.

Everything mirrors the app's own code paths (``src.aggregation``, ``src.geo``,
``src.unmixing.matching``) so the baked numbers match what Streamlit shows;
``--verify`` spot-checks a few cells against a fresh in-process aggregation.

Run from the repo root:
    python scripts/build_static.py --out site/data
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.aggregation import LEVEL_COLS, aggregate_abundances, dominant_archetype
from src.config import load_config
from src.data.loading import load_processed, load_sweep
from src.geo import (
    canonical_province,
    join_municipalities,
    join_provinces,
    join_regions,
    load_municipalities,
    load_provinces,
)
from src.unmixing.matching import match_to_reference

# ---------------------------------------------------------------------------
# What to bake (kept in sync with app/components/{data,constants,sidebar}.py).
# ---------------------------------------------------------------------------
YEARS = ["2025", "2022", "2019"]
DEFAULT_YEAR = YEARS[0]
LEVELS = ["region", "province", "municipality"]  # sidebar excludes "national"
LEVEL_LABELS = {
    "region": "Region",
    "province": "Province",
    "municipality": "City / municipality",
}
VALUE_KINDS = ["Archetype abundance", "Dominant archetype", "Turnout"]
WEIGHTINGS = [True, False]  # ballot-weighted / plain mean

BALLOT_COL = "information.numberOfValidBallot"
VOTERS_COL = "information.numberOfActuallyVoters"
REGISTERED_COL = "information.numberOfRegisteredVoters"
MUNI_COLS = ["REGION", "PROVINCE", "CITY_MUNICIPALITY"]

# Display simplification, matching app/components/map.py.
SIMPLIFY_TOLERANCE = {"municipality": 0.001}
DEFAULT_TOLERANCE = 0.005

ARCH_ROUND = 4  # decimals for abundances/loadings
PCT_ROUND = 2   # decimals for turnout / percentages
COORD_ROUND = 5  # decimals for lon/lat in GeoJSON (~1 m; plenty for display)


def w_tag(weighted: bool) -> str:
    return "w" if weighted else "u"


# ---------------------------------------------------------------------------
# Small helpers replicated from the app layer (avoids a Streamlit dependency).
# ---------------------------------------------------------------------------


def add_turnout(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``turnout_pct`` in place when the voter counts are present
    (mirror of app.components.data.add_turnout)."""
    if VOTERS_COL in df.columns and REGISTERED_COL in df.columns:
        df["turnout_pct"] = 100 * df[VOTERS_COL] / df[REGISTERED_COL]
    return df


def build_level_agg(abundances: pd.DataFrame, level: str, weighted: bool) -> pd.DataFrame:
    """The aggregate the main tab builds for (level, weighting): mean abundances
    per unit + dominant archetype + turnout (mirror of build_view)."""
    arch_cols = [c for c in abundances.columns if c.startswith("arch_")]
    agg = aggregate_abundances(
        abundances, level=level, weight_col=(BALLOT_COL if weighted else None)
    )
    agg["dominant"] = dominant_archetype(agg, arch_cols) if len(agg) else []
    add_turnout(agg)
    return agg


def join_agg_to_boundaries(
    abundances: pd.DataFrame,
    agg: pd.DataFrame,
    level: str,
    weighted: bool,
    provinces,
    municipalities,
):
    """Merge a level aggregate onto its boundaries, mirroring
    app/components/map.py:join_to_boundaries. Returns (gdf, key_col)."""
    if level == "region":
        agg_prov = aggregate_abundances(
            abundances, level="province", weight_col=(BALLOT_COL if weighted else None)
        )
        gdf, _ = join_regions(agg_prov, provinces, agg)
        return gdf, "REGION"
    if level == "province":
        gdf, _ = join_provinces(agg, provinces)
        return gdf, "PROV_KEY"
    gdf, _rate, _unmatched = join_municipalities(agg, municipalities)
    return gdf, "MUNI_ID"


def feature_key(gdf, key_col: str) -> pd.Series:
    """Stable string id per feature, used as the GeoJSON feature id and the
    ``id`` on every value record so the client can join them."""
    if key_col == "MUNI_ID":
        return gdf["PROV_KEY"].astype(str) + "::" + gdf["CITY_MUNICIPALITY"].astype(str)
    return gdf[key_col].astype(str)


def post_join_dominant(gdf, arch_cols: list[str]) -> list[str | None]:
    """Recompute the dominant archetype after the geometry join, exactly as
    app/components/map.py:choropleth_fig does (units may have merged)."""
    dom = dominant_archetype(gdf, arch_cols)
    has_data = gdf[arch_cols[0]].notna().to_numpy()
    return [str(int(d)) if ok else None for d, ok in zip(dom, has_data)]


def _round(x, nd):
    if x is None or (isinstance(x, float) and (np.isnan(x))):
        return None
    return round(float(x), nd)


def records_from_gdf(gdf, key_col: str, arch_cols: list[str]) -> list[dict]:
    """One JSON record per feature: id, arch means, dominant, turnout, counts."""
    keys = feature_key(gdf, key_col).tolist()
    dominant = post_join_dominant(gdf, arch_cols)
    recs = []
    for i, (_, row) in enumerate(gdf.iterrows()):
        rec = {"id": keys[i]}
        for c in arch_cols:
            rec[c] = _round(row.get(c), ARCH_ROUND)
        rec["dominant"] = dominant[i]
        if "turnout_pct" in gdf.columns:
            rec["turnout"] = _round(row.get("turnout_pct"), PCT_ROUND)
        if "n_precincts" in gdf.columns:
            n = row.get("n_precincts")
            rec["n_precincts"] = None if pd.isna(n) else int(n)
        recs.append(rec)
    return recs


def write_geojson(gdf, key_col: str, level: str, path: Path, extra_props=None) -> int:
    """Simplify geometry, set the feature id to the stable key, write GeoJSON.
    Returns bytes written."""
    tol = SIMPLIFY_TOLERANCE.get(level, DEFAULT_TOLERANCE)
    keys = feature_key(gdf, key_col)
    out = gdf[[]].copy()
    out["geometry"] = gdf.geometry.simplify(tol, preserve_topology=True)
    # carry a human-readable name + a few props for hover
    if key_col == "MUNI_ID":
        out["name"] = gdf["CITY_MUNICIPALITY"].astype(str)
        out["prov"] = gdf["PROV_KEY"].astype(str)
    else:
        out["name"] = keys.values
    for k, v in (extra_props or {}).items():
        out[k] = v
    out.index = keys.values  # geopandas writes the index as the feature "id"
    out.index.name = None
    import geopandas as gpd

    gj = json.loads(gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs).to_json())
    for feat in gj.get("features", []):
        geom = feat.get("geometry")
        if geom and geom.get("coordinates") is not None:
            geom["coordinates"] = _round_nested(geom["coordinates"], COORD_ROUND)
    txt = json.dumps(gj, separators=(",", ":"), allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")
    return len(txt.encode("utf-8"))


def _round_nested(coords, nd: int):
    """Round the numbers in an arbitrarily-nested GeoJSON coordinate array."""
    if isinstance(coords, (int, float)):
        return round(coords, nd)
    return [_round_nested(c, nd) for c in coords]


def dump_json(obj, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, separators=(",", ":"), allow_nan=False)
    path.write_text(txt, encoding="utf-8")
    return len(txt.encode("utf-8"))


# ---------------------------------------------------------------------------
# Colors (ported from app/components/theme.py so JS uses identical palettes).
# ---------------------------------------------------------------------------


def theme_payload(arch_counts: set[int]) -> dict:
    import seaborn as sns
    from matplotlib.colors import to_hex

    def categorical(n):
        return [to_hex(c) for c in sns.color_palette("husl", n)]

    def colorscale(name, n=32):
        cmap = sns.color_palette(name, as_cmap=True)
        return [[i / (n - 1), to_hex(cmap(i / (n - 1)))] for i in range(n)]

    return {
        "sequential": colorscale("mako_r"),
        "diverging": colorscale("vlag"),
        "highlight": to_hex(sns.color_palette("vlag", as_cmap=True)(0.88)),
        "categorical": {str(n): categorical(n) for n in sorted(arch_counts)},
    }


# ---------------------------------------------------------------------------
# Sweep baking (mirror of app.components.data.sweep_level_stats).
# ---------------------------------------------------------------------------


def sweep_level_stats(entry: dict, level: str, weighted: bool):
    """(mean_agg, std_agg, mean_muni) across trials at `level` for one sweep p."""
    df = entry["agg_trials"]
    arch_cols_p = [c for c in df.columns if c.startswith("arch_")]
    weight_col = BALLOT_COL if weighted else None

    per_trial = []
    for t, g in df.groupby("trial", observed=True):
        a = aggregate_abundances(
            g, level=level, arch_cols=arch_cols_p, weight_col=weight_col
        )
        a["trial"] = t
        per_trial.append(a)
    stacked = pd.concat(per_trial, ignore_index=True).drop(columns="trial")

    group_cols = LEVEL_COLS[level]
    grouped = stacked.groupby(group_cols, observed=True)
    mean_agg = grouped.mean(numeric_only=True).reset_index()
    std_only = grouped[arch_cols_p].std(ddof=1).reset_index()
    std_agg = mean_agg.copy()
    for c in arch_cols_p:
        std_agg[c] = std_only[c].to_numpy()

    agg_cols = {c: "mean" for c in arch_cols_p}
    agg_cols.update({BALLOT_COL: "first", "n_precincts": "first"})
    mean_muni = df.groupby(MUNI_COLS, observed=True).agg(agg_cols).reset_index()
    return mean_agg, std_agg, mean_muni


def sweep_records(mean_agg, std_agg, arch_cols, level, weighted,
                  provinces, municipalities, mean_muni):
    """(mean_records, std_records) for one sweep (p, level, weighting).

    Mean and std share identical units/geometry, so the boundary join — the
    expensive part at municipality level — is done once on a frame carrying
    both, then split.
    """
    group_cols = LEVEL_COLS[level]
    std_cols = {c: c + "__std" for c in arch_cols}
    combined = mean_agg.merge(
        std_agg[group_cols + arch_cols].rename(columns=std_cols), on=group_cols
    )

    if level == "region":
        agg_prov = aggregate_abundances(
            mean_muni, level="province", arch_cols=arch_cols,
            weight_col=(BALLOT_COL if weighted else None),
        )
        gdf, _ = join_regions(agg_prov, provinces, combined)
        key_col = "REGION"
    elif level == "province":
        gdf, _ = join_provinces(combined, provinces)
        key_col = "PROV_KEY"
    else:
        gdf, _rate, _un = join_municipalities(combined, municipalities)
        key_col = "MUNI_ID"

    keys = feature_key(gdf, key_col).tolist()
    mean_recs, std_recs = [], []
    for i, (_, row) in enumerate(gdf.iterrows()):
        mrec = {"id": keys[i]}
        srec = {"id": keys[i]}
        for c in arch_cols:
            mrec[c] = _round(row.get(c), ARCH_ROUND)
            srec[c] = _round(row.get(c + "__std"), ARCH_ROUND)
        mean_recs.append(mrec)
        std_recs.append(srec)
    return mean_recs, std_recs


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build(out: Path, verify: bool) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    provinces = load_provinces(load_config(REPO_ROOT / "configs" / f"config_{DEFAULT_YEAR}.ini"))
    municipalities = load_municipalities(
        load_config(REPO_ROOT / "configs" / f"config_{DEFAULT_YEAR}.ini")
    )

    sizes: dict[str, int] = {}
    arch_counts: set[int] = set()
    years_meta: dict[str, dict] = {}
    muni_gdfs: list = []  # per-year matched municipal geometries (deduped later)

    # Province geometry is shared across years (full shapefile, left-joined).
    sizes["geo/province.geojson"] = write_geojson(
        provinces.assign(PROV_KEY=provinces["PROV_KEY"]),
        "PROV_KEY",
        "province",
        out / "geo" / "province.geojson",
    )

    for year in YEARS:
        cfg = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
        endmembers, abundances, meta = load_processed(cfg)
        arch_cols = list(endmembers.columns)
        n_arch = len(arch_cols)
        arch_counts.add(n_arch)
        sweep = load_sweep(cfg)

        # --- per-(level, weighting) value tables + per-year geometry ---
        region_geo_written = muni_geo_written = False
        for level in LEVELS:
            for weighted in WEIGHTINGS:
                agg = build_level_agg(abundances, level, weighted)
                gdf, key_col = join_agg_to_boundaries(
                    abundances, agg, level, weighted, provinces, municipalities
                )
                recs = records_from_gdf(gdf, key_col, arch_cols)
                payload = {
                    "year": year,
                    "level": level,
                    "weighted": weighted,
                    "arch_cols": arch_cols,
                    "records": recs,
                }
                rel = f"values/{year}_{level}_{w_tag(weighted)}.json"
                sizes[rel] = dump_json(payload, out / rel)

                # geometry (year-specific for region/municipality) — write once,
                # from the weighted pass (geometry is weighting-independent).
                if weighted and level == "region" and not region_geo_written:
                    sizes[f"geo/{year}_region.geojson"] = write_geojson(
                        gdf, key_col, level, out / "geo" / f"{year}_region.geojson"
                    )
                    region_geo_written = True
                if weighted and level == "municipality" and not muni_geo_written:
                    # Polygons are identical per MUNI_ID across years, so the
                    # geometry is pooled and written once (see below) instead of
                    # one ~1.4 MB file per year.
                    muni_gdfs.append(gdf[["PROV_KEY", "CITY_MUNICIPALITY", "geometry"]])
                    muni_geo_written = True

        # --- endmember loadings + sweep-trial std for the overview tab ---
        loadings_payload = {
            "candidates": list(endmembers.index),
            "arch_cols": arch_cols,
            "mean": {c: [_round(v, ARCH_ROUND) for v in endmembers[c]] for c in arch_cols},
        }
        std_df = _loading_std(endmembers, sweep, meta)
        if std_df is not None:
            loadings_payload["std"] = {
                c: [_round(v, ARCH_ROUND) for v in std_df[c]] for c in arch_cols
            }
        sizes[f"loadings/{year}.json"] = dump_json(
            loadings_payload, out / "loadings" / f"{year}.json"
        )

        # --- sweep detail per p (comparison tab) ---
        for p, entry in sweep.items():
            arch_counts.add(p)  # the comparison tab colors p-archetype loadings
            arch_cols_p = [f"arch_{j}" for j in range(p)]
            lm, ls = entry["loadings_mean"], entry["loadings_std"]
            sw = {
                "year": year,
                "p": p,
                "candidates": list(lm.index),
                "arch_cols": arch_cols_p,
                "loadings_mean": {c: [_round(v, ARCH_ROUND) for v in lm[c]] for c in arch_cols_p},
                "loadings_std": {c: [_round(v, ARCH_ROUND) for v in ls[c]] for c in arch_cols_p},
                "levels": {},
            }
            for level in LEVELS:
                lvl = {}
                for weighted in WEIGHTINGS:
                    mean_agg, std_agg, mean_muni = sweep_level_stats(entry, level, weighted)
                    mean_recs, std_recs = sweep_records(
                        mean_agg, std_agg, arch_cols_p, level, weighted,
                        provinces, municipalities, mean_muni,
                    )
                    lvl[w_tag(weighted)] = {"mean": mean_recs, "std": std_recs}
                sw["levels"][level] = lvl
            rel = f"sweep/{year}_p{p}.json"
            sizes[rel] = dump_json(sw, out / rel)

        years_meta[year] = {
            "n_archetypes": n_arch,
            "candidate_labels": list(endmembers.index),
            "rmse": meta.get("rmse"),
            "sweep_ps": sorted(sweep),
        }

    # --- shared municipality geometry (union across years) ---
    import geopandas as gpd

    pooled = gpd.GeoDataFrame(
        pd.concat(muni_gdfs, ignore_index=True), geometry="geometry",
        crs=muni_gdfs[0].crs,
    )
    pooled["MUNI_ID"] = feature_key(pooled, "MUNI_ID")
    pooled = pooled.drop_duplicates("MUNI_ID").reset_index(drop=True)
    sizes["geo/municipality.geojson"] = write_geojson(
        pooled, "MUNI_ID", "municipality", out / "geo" / "municipality.geojson"
    )

    # --- manifest ---
    manifest = {
        "years": YEARS,
        "default_year": DEFAULT_YEAR,
        "levels": LEVELS,
        "level_labels": LEVEL_LABELS,
        "value_kinds": VALUE_KINDS,
        "weightings": [w_tag(w) for w in WEIGHTINGS],
        "theme": theme_payload(arch_counts),
        "years_meta": years_meta,
    }
    sizes["manifest.json"] = dump_json(manifest, out / "manifest.json")

    total = sum(sizes.values())
    print(f"Wrote {len(sizes)} files to {out} ({total / 1e6:.2f} MB total)")
    for rel in sorted(sizes, key=lambda k: -sizes[k])[:12]:
        print(f"  {sizes[rel] / 1e3:8.1f} KB  {rel}")

    if verify:
        _verify(out, provinces, municipalities)


def _loading_std(endmembers, sweep, meta):
    """Per-loading std borrowed from the sweep, aligned to the single fit
    (mirror of app.components.data.endmember_loading_std)."""
    entry = sweep.get(meta["n_archetypes"])
    if entry is None:
        return None
    mean = entry["loadings_mean"].reindex(endmembers.index)
    std = entry["loadings_std"].reindex(endmembers.index)
    if mean.isna().any().any() or std.isna().any().any():
        return None
    perm, _ = match_to_reference(endmembers.to_numpy(), mean.to_numpy())
    std_aligned = std.iloc[:, perm]
    std_aligned.columns = endmembers.columns
    return std_aligned


def _verify(out: Path, provinces, municipalities) -> None:
    """Spot-check baked values against a fresh in-process aggregation."""
    print("\n== verify ==")
    ok = True
    for year in YEARS:
        cfg = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
        _, abundances, _ = load_processed(cfg)
        for level in LEVELS:
            for weighted in WEIGHTINGS:
                agg = build_level_agg(abundances, level, weighted)
                gdf, key_col = join_agg_to_boundaries(
                    abundances, agg, level, weighted, provinces, municipalities
                )
                recs = records_from_gdf(gdf, key_col, [c for c in agg if c.startswith("arch_")])
                baked = json.loads(
                    (out / f"values/{year}_{level}_{w_tag(weighted)}.json").read_text()
                )["records"]
                if recs != baked:
                    ok = False
                    print(f"  MISMATCH {year} {level} {w_tag(weighted)}")
    print("  all baked value tables reproduce the in-process aggregation"
          if ok else "  VERIFY FAILED")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="site/data", help="output dir (default: site/data)")
    ap.add_argument("--verify", action="store_true", help="spot-check baked values")
    args = ap.parse_args()
    target = Path(args.out)
    build(target if target.is_absolute() else (REPO_ROOT / target).resolve(), args.verify)


if __name__ == "__main__":
    main()
