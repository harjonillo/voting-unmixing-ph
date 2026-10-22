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
    loadings/{year}.json               endmember loadings (mean) + sweep-trial std
                                       (+ NMF only: the NNDSVD run's loadings).
    sweep/{year}_p{p}.json             per-p loadings mean/std (+ NMF only: the
                                       NNDSVD run's) + level stats
                                       (trial mean/std) for the comparison tab.
    lineage/{year}.json                network nodes/links tracing how archetypes
                                       persist/split as p grows across the sweep
                                       (several similarity metrics per
                                       consecutive-p pair, top candidates per
                                       node).
    distinctness/{year}.json           copied from data/distinctness/ (see
                                       Prerequisites).
    order_sensitivity/{year}.json      copied from data/order_sensitivity/ (see
                                       Prerequisites).
    nmf/...                            the same per-year tree (values/, loadings/,
                                       sweep/, lineage/, distinctness/,
                                       order_sensitivity/) for NMF endmembers —
                                       the sidebar's extraction-method switch.
                                       Geometry stays shared at the top level.
                                       Years without NMF outputs are skipped.

Aggregation, matching and geo-join all go through the shared library
(``src.aggregation``, ``src.geo``, ``src.unmixing.matching``), so the baked
numbers match the pipeline; ``--verify`` spot-checks a few cells against a fresh
in-process aggregation.

Prerequisites — two small committed JSON sets this script copies through but
does not compute (it warns if either folder is empty). Both are notebooks
ported to scripts that rerun the experiment for every year from
configs/config_{year}.ini; rerun them after changing a year's data or its
[preprocessing]/[unmixing] config, then rerun this script:

    scripts/bake_distinctness.py       notebook 08: min/mean pairwise distance
                                       between archetypes vs p
                                       -> data/distinctness/.
    scripts/bake_order_sensitivity.py  notebook 09: matched similarity to the
                                       reference under shuffled precinct order
                                       vs varying seed
                                       -> data/order_sensitivity/.

NMF counterparts come from the same scripts with ``--method nmf`` (outputs
under data/processed/<year>/nmf/, data/distinctness/nmf/,
data/order_sensitivity/nmf/). The NMF loadings bars also overlay the
deterministic NNDSVD-initialized run when ``scripts/run_nndsvd.py`` has
written it next to the NMF sweep (optional; skipped silently otherwise).

Run from the repo root:
    python scripts/bake_distinctness.py        # prerequisite (~1 min/year)
    python scripts/bake_order_sensitivity.py   # prerequisite (~5 min/year)
    python scripts/bake_distinctness.py --method nmf       # NMF prerequisites
    python scripts/bake_order_sensitivity.py --method nmf
    python scripts/run_nndsvd.py --config configs/config_{year}.ini  # optional
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
from src.config import load_config, method_path
from src.data.loading import load_processed, load_sweep
from src.geo import (
    canonical_province,
    join_municipalities,
    join_provinces,
    join_regions,
    load_municipalities,
    load_provinces,
)
from src.unmixing import METHODS
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
# Default of the sidebar's archetype-count selector. Every tab shows the sweep's
# trial mean at the selected p (per-level abundances, loadings ± 1 SD); years
# without a sweep fall back to the main (HySime-k) run. Lineage colors (and so
# archetype names and colors at every p) are anchored to the archetypes at this p.
DEFAULT_P = 4

BALLOT_COL = "information.numberOfValidBallot"
VOTERS_COL = "information.numberOfActuallyVoters"
REGISTERED_COL = "information.numberOfRegisteredVoters"

# Display simplification of polygons.
SIMPLIFY_TOLERANCE = {"municipality": 0.001}
DEFAULT_TOLERANCE = 0.005

ARCH_ROUND = 4  # decimals for abundances/loadings
PCT_ROUND = 2  # decimals for turnout / percentages

# Coalition / alliance grouping (the layer *over* parties). Hand-curated from news
# sources; see data/README_coalitions.md. Baked alongside the loadings so the site
# can group the "party mixing" barplot by alliance instead of party.
COALITIONS_CSV = REPO_ROOT / "data" / "elections" / "coalitions_2013-2025.csv"
NO_ALLIANCE = "Independent / none"

# Compare-tab diagnostics baked by their own scripts (notebooks 08/09, rerun per
# year) into small committed JSONs under data/<subdir>/, copied through verbatim
# (data/<subdir>/ -> site/data/<subdir>/) so the CI bake needn't rerun them.
PREBAKED = {
    "distinctness": "scripts/bake_distinctness.py",
    "order_sensitivity": "scripts/bake_order_sensitivity.py",
}


def _norm_label(label: str) -> str:
    """Join key: drop the trailing election-rank "[N]" and collapse whitespace, so
    the site's candidate labels ("GO, BONG GO (PDPLBN) [3]") match the coalition
    CSV's ballot_label ("GO, BONG GO    (PDPLBN)")."""
    return re.sub(r"\s+", " ", re.sub(r"\s*\[\d+\]\s*$", "", label)).strip()


# Display labels: "AQUINO, BENIGNO BAM (LP) [14]" -> "Aquino, Benigno (LP) [14]". Only
# the first given name is kept — later given-name tokens can't be told apart from
# nicknames/slogans ("TULFO, BEN BITAG", "VILLANUEVA, JOEL TESDAMAN"). Names are
# title-cased; the party stays as on the ballot. Ballot honorifics are skipped and
# generational suffixes kept (Enrile Jr. in 2013 vs Enrile Sr. in 2019). Joins
# (coalitions, sweep) use the full labels; these are applied only when serializing.
_HONORIFICS = {
    "ATTY", "ATTORNEY", "DOC", "DR", "DRA", "GEN", "BRO", "MR", "MRS", "MS",
    "KA", "TEACHER", "IDOL", "KUYA", "MANONG", "PRINCESS",
}  # fmt: skip
_SUFFIXES = {"JR": "Jr.", "SR": "Sr.", "II": "II", "III": "III", "IV": "IV"}
# Ballot surnames with a nickname glued on front -> the real surname. Listed by
# hand: real multi-word surnames (DELA ROSA, EJERCITO ESTRADA) look the same.
_NICKNAME_SURNAMES = {"BONG REVILLA": "REVILLA"}
_LABEL_RE = re.compile(
    r"^(?P<name>.*?)\s*(?:\((?P<party>[^)]*)\))?\s*\[(?P<rank>\d+)\]\s*$"
)


def _title(name: str) -> str:
    """'DELA ROSA' -> 'Dela Rosa', 'JUAN-PAOLO' -> 'Juan-Paolo'. Vowel-less tokens
    are initials and stay upper case ('JV', 'TG')."""

    def cap(p: str) -> str:
        return p if not re.search(r"[AEIOU]", p) else p[:1] + p[1:].lower()

    return " ".join("-".join(cap(p) for p in w.split("-")) for w in name.split())


def _display_label(label: str) -> str:
    """'SURNAME, GIVEN NAMES (PARTY) [rank]' -> 'Surname, Given (PARTY) [rank]'.
    Unparseable labels pass through."""
    m = _LABEL_RE.match(label)
    if not m or "," not in m["name"]:
        return label
    surname, given = (s.strip() for s in m["name"].split(",", 1))
    surname = _NICKNAME_SURNAMES.get(surname, surname)
    tokens = [t for t in re.split(r"[\s,.]+", given) if t]
    suffix = [_SUFFIXES[t] for t in tokens if t in _SUFFIXES]
    names = [t for t in tokens if t not in _SUFFIXES]
    while len(names) > 1 and names[0] in _HONORIFICS:
        names = names[1:]
    first = _title(names[0]) if names else ""
    out = f"{_title(surname)}, {' '.join([first, *suffix])}".rstrip(", ")
    if m["party"]:
        out += f" ({m['party']})"
    return f"{out} [{m['rank']}]"


def short_labels(labels) -> dict[str, str]:
    """full -> display label for one year's candidates (the rank keeps any two
    same-named candidates apart)."""
    return {lab: _display_label(lab) for lab in labels}


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


def build_level_agg(
    abundances: pd.DataFrame, level: str, weighted: bool
) -> pd.DataFrame:
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


# Fixed archetype palette: slot i = Archetype i of the main run, never cycled
# (the front-end falls back to a neutral gray past the last slot). The 7th slot
# is for sweep archetypes with no counterpart in the main run (see
# lineage_color_slots). Adjacent pairs pass a colorblind-separation check; three
# slots are under 3:1 on white, so every colored mark in the UI carries a label.
ARCH_PALETTE = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6",
]  # fmt: skip
# Sequential ramp (light -> dark) for the abundance and turnout maps.
SEQUENTIAL_RAMP = [
    "#e8f1fc", "#cde2fb", "#9ec5f4", "#6da7ec",
    "#3987e5", "#256abf", "#184f95", "#0d366b",
]  # fmt: skip
# Diverging ramp (negative -> zero -> positive) for summed-loading tables.
DIVERGING_RAMP = ["#a3302f", "#f0efec", "#184f95"]


def theme_payload() -> dict:
    def colorscale(colors):
        n = len(colors)
        return [[i / (n - 1), c] for i, c in enumerate(colors)]

    return {
        "sequential": colorscale(SEQUENTIAL_RAMP),
        "diverging": colorscale(DIVERGING_RAMP),
        "categorical": ARCH_PALETTE,
    }


# ---------------------------------------------------------------------------
# Sweep baking — reads the per-level trial stats precomputed by run_sweep.py
# (level_stats.parquet) and serializes them; no aggregation happens here.
# ---------------------------------------------------------------------------


def load_level_stats(cfg, p: int, method: str = "mvsa") -> pd.DataFrame:
    """The long-format per-level trial mean/std for sweep p, written by
    scripts/run_sweep.py:level_stats_from_trials."""
    path = method_path(cfg, method, "sweep", f"p{p}", "level_stats.parquet")
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Re-run `python scripts/run_sweep.py "
            f"--config configs/config_<year>.ini --method {method}` — it writes "
            "the per-level trial stats the site build serializes."
        )
    return pd.read_parquet(path)


def _level_frame(
    level_stats: pd.DataFrame,
    level: str,
    weighted: bool,
    stat: str,
    arch_cols: list[str],
    keep_counts: bool,
) -> pd.DataFrame:
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
    mean_agg = _level_frame(
        level_stats, level, weighted, "mean", arch_cols, keep_counts=True
    )
    std_agg = _level_frame(
        level_stats, level, weighted, "std", arch_cols, keep_counts=False
    )

    if level == "region":
        mean_recs = [
            _rec(str(r["REGION"]), r, arch_cols) for _, r in mean_agg.iterrows()
        ]
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
        mean_recs.append(
            {"id": keys_i, **{c: _round(row.get(c), ARCH_ROUND) for c in arch_cols}}
        )
        std_recs.append(
            {
                "id": keys_i,
                **{c: _round(row.get(c + "__std"), ARCH_ROUND) for c in arch_cols},
            }
        )
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
# so the client can list the top 6–12. The per-p min/mean pairwise distances
# shown above each column come from distinctness/{year}.json
# (scripts/bake_distinctness.py), not from here.
# ---------------------------------------------------------------------------

LINEAGE_TOP_K = 12  # candidates baked per node; the client shows the top 6–12

# Edge metrics baked per archetype pair (the client's similarity selector).
LINEAGE_METRICS = {
    "cos12": cosine_topk_matrix,
    "cos": cosine_matrix,
    "spearman": spearman_matrix,
    "wtau": weighted_tau_matrix,
    "rbo": rbo_matrix,
    "jac12": topk_jaccard_matrix,
}


def _short_label(label: str) -> str:
    """Surname for a compact node label: 'GO, BONG GO (PDPLBN) [3]' -> 'Go'."""
    surname = str(label).split(" [")[0].split(",")[0].strip()
    return _NICKNAME_SURNAMES.get(surname, surname).title()


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


def lineage_color_slots(
    ps: list[int], edges: list[dict], anchor: dict[int, int] | None, p_anchor: int
) -> dict[tuple[int, int], int]:
    """(p, k) -> palette slot, so an archetype keeps one color across the sweep.

    At p_anchor, sweep archetype k takes the slot of its main-run counterpart
    (`anchor`: sweep k -> main-run index; identity when None). Slots then follow
    the Hungarian-matched links backwards to ps[0] (every archetype at p - 1 is
    matched to one at p) and forwards to ps[-1], where each step's leftover
    "split" child takes the next free slot."""
    matched = {
        (e["p_from"], e["k_from"]): (e["p_to"], e["k_to"]) for e in edges if not e["split"]
    }
    slots = {(p_anchor, k): (anchor or {}).get(k, k) for k in range(p_anchor)}
    below = [p for p in ps if p < p_anchor][::-1]
    for p in below:
        for k in range(p):
            child = matched.get((p, k))
            slots[(p, k)] = slots[child] if child in slots else k
    nxt = max(slots.values(), default=-1) + 1
    for p_from, p_to in zip(ps, ps[1:]):
        if p_to <= p_anchor:
            continue
        for k in range(p_from):
            child = matched.get((p_from, k))
            if child is not None:
                slots[child] = slots[(p_from, k)]
        for k in range(p_to):
            if (p_to, k) not in slots:
                slots[(p_to, k)] = nxt
                nxt += 1
    return slots


def build_lineage(
    year: str,
    sweep: dict,
    short: dict[str, str],
    endmembers: pd.DataFrame | None = None,
) -> dict:
    """Lineage network tracing how archetypes persist or split as p grows
    across the sweep. Independent of level/weighting — driven only by
    loadings_mean. `short` maps full candidate labels to display labels.
    Each node's ``color_slot`` is anchored to the sweep's own columns at
    DEFAULT_P when the sweep has it, else to the main run (`endmembers`)
    matched onto the sweep at its p."""
    ps = sorted(sweep)
    mats = {p: sweep[p]["loadings_mean"].to_numpy() for p in ps}
    edges = archetype_lineage(mats)
    lineage = {(e["p_from"], e["k_from"], e["p_to"], e["k_to"]): e for e in edges}

    # Anchor at the sweep's columns at DEFAULT_P as they are, else the main run's
    # p (Hungarian match of the sweep mean onto it, as in _loadings_from_sweep);
    # with neither, colors start at ps[0].
    p_anchor, anchor = ps[0], None
    if DEFAULT_P in sweep:
        p_anchor = DEFAULT_P
    elif endmembers is not None and endmembers.shape[1] in sweep:
        mean = sweep[endmembers.shape[1]]["loadings_mean"].reindex(endmembers.index)
        if not mean.isna().any().any():
            perm, _ = match_to_reference(endmembers.to_numpy(), mean.to_numpy())
            p_anchor = endmembers.shape[1]
            anchor = {int(k): i for i, k in enumerate(perm)}
    slots = lineage_color_slots(ps, edges, anchor, p_anchor)

    node_index: dict[tuple[int, int], int] = {}
    nodes: list[dict] = []
    for p in ps:
        lm = sweep[p]["loadings_mean"]
        for k in range(p):
            node_index[(p, k)] = len(nodes)
            top = lm.iloc[:, k].sort_values(ascending=False).head(LINEAGE_TOP_K)
            names = _node_names(list(top.index))
            nodes.append(
                {
                    "p": p,
                    "k": k,
                    "color_slot": slots[(p, k)],
                    "label": _short_label(top.index[0]),
                    "top": [
                        {"name": nm, "full": short[c], "w": _round(w, ARCH_ROUND)}
                        for nm, (c, w) in zip(names, top.items())
                    ],
                }
            )

    links: list[dict] = []
    for p_from, p_to in zip(ps[:-1], ps[1:]):
        sims = {
            name: fn(mats[p_from], mats[p_to]) for name, fn in LINEAGE_METRICS.items()
        }
        for i in range(p_from):
            for j in range(p_to):
                e = lineage.get((p_from, i, p_to, j))
                links.append(
                    {
                        "source": node_index[(p_from, i)],
                        "target": node_index[(p_to, j)],
                        "sims": {n: round(float(S[i, j]), 3) for n, S in sims.items()},
                        "matched": e is not None and not e["split"],
                        "split": e is not None and bool(e["split"]),
                    }
                )

    return {
        "year": year,
        "ps": ps,
        "anchor_p": p_anchor,
        "nodes": nodes,
        "links": links,
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def method_dir(out: Path, method: str) -> Path:
    """Where one method's per-year data lives: MVSA at the top of ``out`` (the
    original layout), every other method in ``out``/<method>/ (same layout)."""
    return out if method == "mvsa" else out / method


def bake_year(
    year: str,
    method: str,
    out: Path,
    provinces,
    municipalities,
    amap: dict,
    sizes: dict[str, int],
    geo: dict | None,
) -> dict | None:
    """Bake one (year, method): value tables, loadings, sweep detail and lineage
    under ``method_dir(out, method)``. Returns the manifest's years_meta entry,
    or None when that method's pipeline outputs don't exist for the year.

    `geo` (MVSA pass only) collects the year's region GeoJSON + municipal
    geometry; geometry is method-independent, so other methods skip it."""
    cfg = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
    if not method_path(cfg, method, "endmembers.csv").exists():
        if method == "mvsa":
            raise FileNotFoundError(f"no MVSA pipeline outputs for {year}")
        print(
            f"  (!) {year}: no {METHODS[method]} outputs — run `python "
            f"scripts/run_pipeline.py --config configs/config_{year}.ini --method "
            f"{method}` (and run_sweep.py) to add it; skipped"
        )
        return None
    root = method_dir(out, method)
    rel_root = root.relative_to(out)
    endmembers, abundances, meta = load_processed(cfg, method)
    arch_cols = list(endmembers.columns)
    n_arch = len(arch_cols)
    sweep = load_sweep(cfg, method=method)
    short = short_labels(
        dict.fromkeys(
            [*endmembers.index, *(c for e in sweep.values() for c in e["loadings_mean"].index)]
        )
    )

    def write(rel: str, obj) -> None:
        sizes[str(rel_root / rel)] = dump_json(obj, root / rel)

    # --- per-(level, weighting) value tables + per-year geometry ---
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
            write(f"values/{year}_{level}_{w_tag(weighted)}.json", payload)

            # geometry (year-specific for region/municipality) — written once,
            # from the MVSA weighted pass (geometry is method- and
            # weighting-independent).
            if geo is not None and weighted and level == "region":
                sizes[f"geo/{year}_region.geojson"] = write_geojson(
                    gdf, key_col, level, out / "geo" / f"{year}_region.geojson"
                )
            if geo is not None and weighted and level == "municipality":
                # Polygons are identical per MUNI_ID across years, so the
                # geometry is pooled and written once (see build) instead of
                # one ~1.4 MB file per year.
                geo["muni_gdfs"].append(
                    gdf[["PROV_KEY", "CITY_MUNICIPALITY", "geometry"]]
                )

    # --- endmember loadings + sweep-trial std for the overview tab ---
    loadings_payload = {
        "candidates": [short[c] for c in endmembers.index],
        "arch_cols": arch_cols,
        "mean": {c: [_round(v, ARCH_ROUND) for v in endmembers[c]] for c in arch_cols},
        **alliance_arrays(year, list(endmembers.index), amap),
    }
    std_df, nndsvd_df = _loadings_from_sweep(endmembers, sweep, meta)
    if std_df is not None:
        loadings_payload["std"] = {
            c: [_round(v, ARCH_ROUND) for v in std_df[c]] for c in arch_cols
        }
    if nndsvd_df is not None:
        loadings_payload["nndsvd"] = {
            c: [_round(v, ARCH_ROUND) for v in nndsvd_df[c]] for c in arch_cols
        }
    write(f"loadings/{year}.json", loadings_payload)

    # --- sweep detail per p (comparison tab) ---
    for p, entry in sweep.items():
        arch_cols_p = [f"arch_{j}" for j in range(p)]
        lm, ls = entry["loadings_mean"], entry["loadings_std"]
        level_stats = load_level_stats(cfg, p, method)  # precomputed by run_sweep.py
        sw = {
            "year": year,
            "p": p,
            "candidates": [short[c] for c in lm.index],
            "arch_cols": arch_cols_p,
            "loadings_mean": {
                c: [_round(v, ARCH_ROUND) for v in lm[c]] for c in arch_cols_p
            },
            "loadings_std": {
                c: [_round(v, ARCH_ROUND) for v in ls[c]] for c in arch_cols_p
            },
            **alliance_arrays(year, list(lm.index), amap),
            "levels": {},
        }
        if "loadings_nndsvd" in entry:  # NMF only (run_nndsvd.py), aligned to lm
            ln = entry["loadings_nndsvd"].reindex(lm.index)
            sw["loadings_nndsvd"] = {
                c: [_round(v, ARCH_ROUND) for v in ln[c]] for c in arch_cols_p
            }
            sw["nndsvd_meta"] = entry["nndsvd_meta"]
        for level in LEVELS:
            lvl = {}
            for weighted in WEIGHTINGS:
                mean_recs, std_recs = sweep_records(
                    level_stats,
                    arch_cols_p,
                    level,
                    weighted,
                    provinces,
                    municipalities,
                )
                lvl[w_tag(weighted)] = {"mean": mean_recs, "std": std_recs}
            sw["levels"][level] = lvl
        write(f"sweep/{year}_p{p}.json", sw)

    # --- archetype lineage across the whole sweep (comparison network) ---
    if len(sweep) > 1:
        write(f"lineage/{year}.json", build_lineage(year, sweep, short, endmembers))

    return {
        "n_archetypes": n_arch,
        "candidate_labels": [short[c] for c in endmembers.index],
        "rmse": meta.get("rmse"),
        "hysime_kf": meta.get("hysime_kf"),
        "sweep_ps": sorted(sweep),
        "sweep_trials": next(
            (e["meta"].get("n_trials") for e in sweep.values() if "meta" in e), None
        ),
        # mean reconstruction RMSE over the sweep's trials, per p
        "sweep_rmse": {
            str(p): e.get("meta", {}).get("rmse_mean") for p, e in sorted(sweep.items())
        },
    }


def build(out: Path, verify: bool, methods: list[str] | None = None) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    provinces = load_provinces(
        load_config(REPO_ROOT / "configs" / f"config_{DEFAULT_YEAR}.ini")
    )
    municipalities = load_municipalities(
        load_config(REPO_ROOT / "configs" / f"config_{DEFAULT_YEAR}.ini")
    )

    sizes: dict[str, int] = {}
    geo = {"muni_gdfs": []}  # per-year matched municipal geometries (deduped later)

    # Province geometry is shared across years (full shapefile, left-joined).
    sizes["geo/province.geojson"] = write_geojson(
        provinces.assign(PROV_KEY=provinces["PROV_KEY"]),
        "PROV_KEY",
        "province",
        out / "geo" / "province.geojson",
    )

    amap = load_alliance_map()

    methods_meta: dict[str, dict] = {}
    for method, label in METHODS.items():
        if methods and method not in methods:
            continue
        print(f"== {label} ==")
        years_meta: dict[str, dict] = {}
        for year in YEARS:
            entry = bake_year(
                year,
                method,
                out,
                provinces,
                municipalities,
                amap,
                sizes,
                geo if method == "mvsa" else None,
            )
            if entry is not None:
                years_meta[year] = entry
        if years_meta:
            methods_meta[method] = {
                "label": label,
                "base": "" if method == "mvsa" else method,
                "years": [y for y in YEARS if y in years_meta],
                "years_meta": years_meta,
            }

    # --- shared municipality geometry (union across years) ---
    import geopandas as gpd

    muni_gdfs = geo["muni_gdfs"]
    pooled = gpd.GeoDataFrame(
        pd.concat(muni_gdfs, ignore_index=True),
        geometry="geometry",
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
        "theme": theme_payload(),
        # extraction method -> {label, base (data subdir, "" = top level),
        # years (those with data), years_meta}
        "default_method": "mvsa",
        "default_p": DEFAULT_P,
        "methods": methods_meta,
    }
    sizes["manifest.json"] = dump_json(manifest, out / "manifest.json")

    # --- pre-baked compare-tab diagnostics (see PREBAKED) ---
    # data/<sub>/*.json (MVSA) -> <out>/<sub>/, data/<sub>/<method>/*.json ->
    # <out>/<method>/<sub>/, mirroring method_dir.
    for sub, script in PREBAKED.items():
        for method in methods_meta:
            src = REPO_ROOT / "data" / sub
            if method != "mvsa":
                src = src / method
            files = sorted(src.glob("*.json"))
            if not files:
                flag = "" if method == "mvsa" else f" --method {method}"
                print(f"WARNING: {src.relative_to(REPO_ROOT)}/ is empty — run {script}{flag} first")
            dest = method_dir(out, method) / sub
            for f in files:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest / f.name)
                sizes[str((dest / f.name).relative_to(out))] = f.stat().st_size

    total = sum(sizes.values())
    print(f"Wrote {len(sizes)} files to {out} ({total / 1e6:.2f} MB total)")
    for rel in sorted(sizes, key=lambda k: -sizes[k])[:12]:
        print(f"  {sizes[rel] / 1e3:8.1f} KB  {rel}")

    if verify:
        _verify(out, provinces, municipalities, methods_meta)


def _loadings_from_sweep(endmembers, sweep, meta):
    """(std, nndsvd) loadings borrowed from the sweep at the single fit's p,
    aligned to the single fit: the per-candidate std of the loading across the
    sweep's trials, and the deterministic NNDSVD run's loadings (NMF only;
    None when absent). Both share the sweep mean's column order, so one
    Hungarian match of the mean onto the fit aligns them. (None, None) when the
    sweep lacks that p or its candidates."""
    entry = sweep.get(meta["n_archetypes"])
    if entry is None:
        return None, None
    mean = entry["loadings_mean"].reindex(endmembers.index)
    std = entry["loadings_std"].reindex(endmembers.index)
    if mean.isna().any().any() or std.isna().any().any():
        return None, None
    perm, _ = match_to_reference(endmembers.to_numpy(), mean.to_numpy())

    def aligned(df):
        df = df.iloc[:, perm]
        df.columns = endmembers.columns
        return df

    nndsvd = entry.get("loadings_nndsvd")
    if nndsvd is not None:
        nndsvd = nndsvd.reindex(endmembers.index)
        nndsvd = None if nndsvd.isna().any().any() else aligned(nndsvd)
    return aligned(std), nndsvd


def _verify(out: Path, provinces, municipalities, methods_meta: dict) -> None:
    """Spot-check baked values against a fresh in-process aggregation."""
    print("\n== verify ==")
    ok = True
    for method, mm in methods_meta.items():
        for year in mm["years"]:
            cfg = load_config(REPO_ROOT / "configs" / f"config_{year}.ini")
            _, abundances, _ = load_processed(cfg, method)
            root = method_dir(out, method)
            for level in LEVELS:
                for weighted in WEIGHTINGS:
                    agg = build_level_agg(abundances, level, weighted)
                    gdf, key_col = join_agg_to_boundaries(
                        abundances, agg, level, weighted, provinces, municipalities
                    )
                    recs = records_from_gdf(
                        gdf, key_col, [c for c in agg if c.startswith("arch_")]
                    )
                    baked = json.loads(
                        (root / f"values/{year}_{level}_{w_tag(weighted)}.json").read_text()
                    )["records"]
                    if recs != baked:
                        ok = False
                        print(f"  MISMATCH {method} {year} {level} {w_tag(weighted)}")
    print(
        "  all baked value tables reproduce the in-process aggregation"
        if ok
        else "  VERIFY FAILED"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", default="site/data", help="output dir (default: site/data)"
    )
    ap.add_argument("--verify", action="store_true", help="spot-check baked values")
    ap.add_argument(
        "--methods",
        nargs="+",
        choices=list(METHODS),
        default=None,
        help="extraction methods to bake (default: all; mvsa is always needed "
        "for the shared geometry)",
    )
    args = ap.parse_args()
    if args.methods and "mvsa" not in args.methods:
        ap.error("--methods must include mvsa (it writes the shared geometry)")
    target = Path(args.out)
    build(
        target if target.is_absolute() else (REPO_ROOT / target).resolve(),
        args.verify,
        args.methods,
    )


if __name__ == "__main__":
    main()
