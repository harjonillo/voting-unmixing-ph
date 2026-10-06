"""Bake the voting-archetype explorer into a fully static dataset.

The explorer does no on-demand computation beyond cheap pandas aggregation,
argmax, a tiny Hungarian match, a geo-join and Plotly rendering. The user's
input space is small and enumerable, so this script pre-computes every
combination offline and writes plain JSON + simplified GeoJSON. A static
front-end (FastHTML shell + Plotly.js) then only loads a file and draws — no
Pyodide, no scientific stack in the browser.

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
    lineage/{year}.json                network nodes/links tracing how archetypes
                                       persist/split as p grows across the sweep
                                       (several similarity metrics per
                                       consecutive-p pair, top candidates per
                                       node, within-p min/mean distances).

Aggregation, matching and geo-join all go through the shared library
(``src.aggregation``, ``src.geo``, ``src.unmixing.matching``), so the baked
numbers match the pipeline; ``--verify`` spot-checks a few cells against a fresh
in-process aggregation.

Run from the repo root:
    python scripts/build_static.py --out site/data
"""

from __future__ import annotations

import argparse
import csv
import json
import re
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
from src.unmixing.matching import (
    archetype_lineage,
    cosine_matrix,
    cosine_topk_matrix,
    match_to_reference,
    rbo_matrix,
    spearman_matrix,
    topk_jaccard_matrix,
    weighted_tau_matrix,
)

# ---------------------------------------------------------------------------
# What to bake (this file is the single source of truth for the site data contract).
# ---------------------------------------------------------------------------
YEARS = ["2025", "2022", "2019", "2016", "2013"]
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

# Display simplification of polygons.
SIMPLIFY_TOLERANCE = {"municipality": 0.001}
DEFAULT_TOLERANCE = 0.005

ARCH_ROUND = 4  # decimals for abundances/loadings
PCT_ROUND = 2   # decimals for turnout / percentages

# Coalition / alliance grouping (the layer *over* parties). Hand-curated from news
# sources; see data/README_coalitions.md. Baked alongside the loadings so the site
# can group the "party mixing" barplot by alliance instead of party.
COALITIONS_CSV = REPO_ROOT / "data" / "elections" / "coalitions_2013-2025.csv"
NO_ALLIANCE = "Independent / none"


def _norm_label(label: str) -> str:
    """Join key: drop the trailing election-rank "[N]" and collapse whitespace, so
    the site's candidate labels ("GO, BONG GO (PDPLBN) [3]") match the coalition
    CSV's ballot_label ("GO, BONG GO    (PDPLBN)")."""
    return re.sub(r"\s+", " ", re.sub(r"\s*\[\d+\]\s*$", "", label)).strip()


def _alliance_view(rows: list[dict]) -> tuple[list[str], str]:
    """Reduce a candidate's coalition rows to (list-of-slates, detail-string).

    A candidate can sit on several slates (guest / cross-endorsement). Rather than
    force them into a single bucket, we return **every** real slate they ran with,
    so the grouped view can list them under each one (with an "also in …" note).
    `list` is core-first then alphabetical; `detail` is the full membership string
    for the party-mode side table. An empty list means independent / no slate."""
    real = [r for r in rows if r["coalition"] != NO_ALLIANCE]
    if not real:
        return [], NO_ALLIANCE
    ordered = sorted(real, key=lambda r: (r["membership"] != "core", r["coalition"]))
    slates = [r["coalition"] for r in ordered]
    detail = ", ".join(f'{r["coalition"]} ({r["membership"]})' for r in ordered)
    return slates, detail


def load_alliance_map() -> dict[str, dict[str, tuple[list[str], str]]]:
    """year -> normalized-ballot-label -> (slates, detail). Empty if the CSV is
    missing (the site then just falls back to party-only grouping)."""
    if not COALITIONS_CSV.exists():
        print(f"  (!) {COALITIONS_CSV} not found — alliance grouping will be empty")
        return {}
    by_cand: dict[str, dict[str, list[dict]]] = {}
    with open(COALITIONS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = _norm_label(r["ballot_label"])
            by_cand.setdefault(r["year"], {}).setdefault(key, []).append(r)
    return {
        year: {key: _alliance_view(rows) for key, rows in cands.items()}
        for year, cands in by_cand.items()
    }


def alliance_arrays(year: str, labels: list[str], amap: dict) -> dict:
    """Per-candidate `list`/`detail` arrays aligned to `labels` (endmember order).
    `alliance_list[i]` is every slate candidate i ran with (guests appear in each);
    the front-end places the candidate under each and annotates the others."""
    ym = amap.get(year, {})
    slates, details = [], []
    for lab in labels:
        lst, detail = ym.get(_norm_label(lab), ([], NO_ALLIANCE))
        slates.append(lst)
        details.append(detail)
    return {"alliance_list": slates, "alliance_detail": details}
COORD_ROUND = 5  # decimals for lon/lat in GeoJSON (~1 m; plenty for display)


def w_tag(weighted: bool) -> str:
    return "w" if weighted else "u"


# ---------------------------------------------------------------------------
# Small self-contained aggregation / turnout helpers.
# ---------------------------------------------------------------------------


def add_turnout(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``turnout_pct`` in place when the voter counts are present
    (adds a per-unit turnout_pct column)."""
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
    """Merge a level aggregate onto its boundaries via the shared geo helpers.
    Returns (gdf, key_col)."""
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
    """Recompute the dominant archetype after the geometry join (units may have
    merged)."""
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
# Colors: baked into the manifest so the JS front-end uses identical palettes.
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
# Sweep baking — reads the per-level trial stats precomputed by run_sweep.py
# (level_stats.parquet) and serializes them; no aggregation happens here.
# ---------------------------------------------------------------------------


def load_level_stats(cfg, p: int) -> pd.DataFrame:
    """The long-format per-level trial mean/std for sweep p, written by
    scripts/run_sweep.py:level_stats_from_trials."""
    from src.config import processed_path

    path = processed_path(cfg, "sweep", f"p{p}", "level_stats.parquet")
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Re-run `python scripts/run_sweep.py "
            "--config configs/config_<year>.ini` — it now writes the per-level "
            "trial stats the site build serializes."
        )
    return pd.read_parquet(path)


def _level_frame(level_stats: pd.DataFrame, level: str, weighted: bool, stat: str,
                 arch_cols: list[str], keep_counts: bool) -> pd.DataFrame:
    """Slice one (level, weighting, stat) table out of the long-format stats,
    keeping only that level's key columns (and, optionally, the count columns)."""
    group_cols = LEVEL_COLS[level]
    cols = group_cols + (["n_precincts", BALLOT_COL] if keep_counts else []) + arch_cols
    sel = level_stats[
        (level_stats["level"] == level)
        & (level_stats["weighted"] == weighted)
        & (level_stats["stat"] == stat)
    ]
    return sel[cols].reset_index(drop=True)


def sweep_records(level_stats, arch_cols, level, weighted, provinces, municipalities):
    """(mean_records, std_records) for one sweep (p, level, weighting), keyed to
    the GeoJSON feature ids.

    Region stats are already keyed by REGION (= the region GeoJSON feature id),
    so they need no geometry join. Province/municipality stats are joined to the
    boundaries to canonicalize / name-match their key; mean and std ride one
    join together (split afterward)."""
    mean_agg = _level_frame(level_stats, level, weighted, "mean", arch_cols, keep_counts=True)
    std_agg = _level_frame(level_stats, level, weighted, "std", arch_cols, keep_counts=False)

    if level == "region":
        mean_recs = [_rec(str(r["REGION"]), r, arch_cols) for _, r in mean_agg.iterrows()]
        std_recs = [_rec(str(r["REGION"]), r, arch_cols) for _, r in std_agg.iterrows()]
        return mean_recs, std_recs

    group_cols = LEVEL_COLS[level]
    std_cols = {c: c + "__std" for c in arch_cols}
    combined = mean_agg.merge(
        std_agg[group_cols + arch_cols].rename(columns=std_cols), on=group_cols
    )
    if level == "province":
        gdf, _ = join_provinces(combined, provinces)
        key_col = "PROV_KEY"
    else:
        gdf, _rate, _un = join_municipalities(combined, municipalities)
        key_col = "MUNI_ID"

    keys = feature_key(gdf, key_col).tolist()
    mean_recs, std_recs = [], []
    for i, (_, row) in enumerate(gdf.iterrows()):
        keys_i = keys[i]
        mean_recs.append({"id": keys_i, **{c: _round(row.get(c), ARCH_ROUND) for c in arch_cols}})
        std_recs.append({"id": keys_i, **{c: _round(row.get(c + "__std"), ARCH_ROUND) for c in arch_cols}})
    return mean_recs, std_recs


def _rec(key: str, row, arch_cols) -> dict:
    return {"id": key, **{c: _round(row[c], ARCH_ROUND) for c in arch_cols}}


# ---------------------------------------------------------------------------
# Archetype lineage — the comparison-tab network. Nodes are the (p, k)
# archetypes of the sweep, pinned per-p; links carry several similarity
# metrics (LINEAGE_METRICS) for *every* archetype pair in consecutive p's,
# with the Hungarian match (`matched`, full-cosine) and the leftover-child
# flag (`split`) from `archetype_lineage` marked on top, so the client can
# emphasise the lineage and fade the rest. Each node bakes its top candidates
# so the client can list the top 6–12; per-p min/mean pairwise distances
# (notebook 08's distinctness scalars) ride along for the column readout.
# ---------------------------------------------------------------------------

LINEAGE_TOP_K = 12  # candidates baked per node; the client shows the top 6–12

# Edge metrics baked per archetype pair (the client's similarity selector).
# `signed` marks [-1, 1] metrics, mapped to a 0..1 distance as (1 - s) / 2;
# unsigned [0, 1] metrics map as 1 - s (notebook 08's `to_distance`).
LINEAGE_METRICS = {
    "cos12": dict(fn=cosine_topk_matrix, signed=True),
    "cos": dict(fn=cosine_matrix, signed=True),
    "spearman": dict(fn=spearman_matrix, signed=True),
    "wtau": dict(fn=weighted_tau_matrix, signed=True),
    "rbo": dict(fn=rbo_matrix, signed=False),
    "jac12": dict(fn=topk_jaccard_matrix, signed=False),
}


def _to_distance(S: np.ndarray, signed: bool) -> np.ndarray:
    return (1.0 - S) / 2.0 if signed else 1.0 - S


def _short_label(label: str) -> str:
    """Surname for a compact node label: 'GO, BONG GO (PDPLBN) [3]' -> 'Go'."""
    return str(label).split(" [")[0].split(",")[0].title()


def _node_names(labels: list[str]) -> list[str]:
    """Compact display names for one node's candidate list: surname only, with a
    given-name initial prepended wherever two candidates in the same node share
    a surname ('Tulfo' + 'Tulfo' -> 'B. Tulfo' + 'E. Tulfo')."""
    surnames = [_short_label(c) for c in labels]
    dupes = {s for s in surnames if surnames.count(s) > 1}
    names = []
    for c, s in zip(labels, surnames):
        given = str(c).split(" [")[0].partition(",")[2]
        given = re.sub(r"\s*\([^)]*\)\s*$", "", given).strip()
        names.append(f"{given[0]}. {s}" if s in dupes and given else s)
    return names


def build_lineage(year: str, sweep: dict) -> dict:
    """Lineage network tracing how archetypes persist or split as p grows
    across the sweep. Independent of level/weighting — driven only by
    loadings_mean."""
    ps = sorted(sweep)
    mats = {p: sweep[p]["loadings_mean"].to_numpy() for p in ps}
    lineage = {
        (e["p_from"], e["k_from"], e["p_to"], e["k_to"]): e
        for e in archetype_lineage(mats)
    }

    node_index: dict[tuple[int, int], int] = {}
    nodes: list[dict] = []
    for p in ps:
        lm = sweep[p]["loadings_mean"]
        for k in range(p):
            node_index[(p, k)] = len(nodes)
            top = lm.iloc[:, k].sort_values(ascending=False).head(LINEAGE_TOP_K)
            names = _node_names(list(top.index))
            nodes.append({
                "p": p,
                "k": k,
                "label": _short_label(top.index[0]),
                "top": [
                    {"name": nm, "full": str(c), "w": _round(w, ARCH_ROUND)}
                    for nm, (c, w) in zip(names, top.items())
                ],
            })

    links: list[dict] = []
    for p_from, p_to in zip(ps[:-1], ps[1:]):
        sims = {
            name: m["fn"](mats[p_from], mats[p_to])
            for name, m in LINEAGE_METRICS.items()
        }
        for i in range(p_from):
            for j in range(p_to):
                e = lineage.get((p_from, i, p_to, j))
                links.append({
                    "source": node_index[(p_from, i)],
                    "target": node_index[(p_to, j)],
                    "sims": {n: round(float(S[i, j]), 3) for n, S in sims.items()},
                    "matched": e is not None and not e["split"],
                    "split": e is not None and bool(e["split"]),
                })

    # Within-p distinctness scalars (notebook 08): the p×p distance matrix of
    # each metric collapsed to its min / mean off-diagonal, per column.
    distinct: dict[int, dict] = {}
    for p in ps:
        per = {}
        for name, m in LINEAGE_METRICS.items():
            D = _to_distance(m["fn"](mats[p], mats[p]), m["signed"])
            off = D[np.triu_indices(p, 1)]
            per[name] = {
                "min": round(float(off.min()), 3),
                "mean": round(float(off.mean()), 3),
            }
        distinct[p] = per

    return {"year": year, "ps": ps, "nodes": nodes, "links": links,
            "distinct": distinct}


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

    amap = load_alliance_map()

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
            **alliance_arrays(year, list(endmembers.index), amap),
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
            level_stats = load_level_stats(cfg, p)  # precomputed by run_sweep.py
            sw = {
                "year": year,
                "p": p,
                "candidates": list(lm.index),
                "arch_cols": arch_cols_p,
                "loadings_mean": {c: [_round(v, ARCH_ROUND) for v in lm[c]] for c in arch_cols_p},
                "loadings_std": {c: [_round(v, ARCH_ROUND) for v in ls[c]] for c in arch_cols_p},
                **alliance_arrays(year, list(lm.index), amap),
                "levels": {},
            }
            for level in LEVELS:
                lvl = {}
                for weighted in WEIGHTINGS:
                    mean_recs, std_recs = sweep_records(
                        level_stats, arch_cols_p, level, weighted, provinces, municipalities
                    )
                    lvl[w_tag(weighted)] = {"mean": mean_recs, "std": std_recs}
                sw["levels"][level] = lvl
            rel = f"sweep/{year}_p{p}.json"
            sizes[rel] = dump_json(sw, out / rel)

        # --- archetype lineage across the whole sweep (comparison network) ---
        if len(sweep) > 1:
            sizes[f"lineage/{year}.json"] = dump_json(
                build_lineage(year, sweep), out / "lineage" / f"{year}.json"
            )

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
    (per-candidate std of the loading across the sweep's trials)."""
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
