"""Boundary loading and COMELEC ↔ shapefile name matching.

Region shapes are NOT taken from the (pre-2024) region shapefile: COMELEC 2025
regions include BARMM and the Negros Island Region, which old shapefiles lack.
Instead, provinces are matched by name and dissolved into regions using the
province→region assignment observed in the election data itself.
"""

import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import shapefile_path

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Uppercase, ASCII-fold, strip punctuation/extra spaces."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return " ".join(s.split())


def compact_key(name: str) -> str:
    """Normalized name with spaces removed — GADM's low-resolution files ship
    names without spaces ("CamarinesSur"), so all lookups use compact keys."""
    return normalize_name(name).replace(" ", "")


# Data-side canonicalization: COMELEC province value -> shapefile province.
# Applied AFTER normalize_name. Extend as the match report demands.
PROVINCE_ALIASES = {
    # 2022 split of Maguindanao; old shapefiles have the undivided province
    "MAGUINDANAO DEL NORTE": "MAGUINDANAO",
    "MAGUINDANAO DEL SUR": "MAGUINDANAO",
    # 2019 rename
    "DAVAO DE ORO": "COMPOSTELA VALLEY",
    # created 2013; older shapefiles only have the parent province
    "DAVAO OCCIDENTAL": "DAVAO DEL SUR",
    # BARMM Special Geographic Area: barangays geographically in Cotabato
    "SPECIAL GEOGRAPHIC AREA": "COTABATO",
    # nullified 2008, merged back into Maguindanao
    "SHARIFF KABUNSUAN": "MAGUINDANAO",
}

# NCR is one "province" in shapefiles but several districts in COMELEC data.
NCR_CANONICAL = "METROPOLITAN MANILA"


def canonical_province(province: str, region: str) -> str:
    """Map a COMELEC PROVINCE value to the shapefile-era province name."""
    p = normalize_name(province)
    if normalize_name(region) == "NCR":
        return NCR_CANONICAL
    return PROVINCE_ALIASES.get(p, p)


# ---------------------------------------------------------------------------
# Boundary loading
# ---------------------------------------------------------------------------

def _detect_name_column(gdf: gpd.GeoDataFrame, candidates=("PROVINCE", "NAME_1", "NAME", "PROV_NAME", "ADM2_EN", "ADM1_EN")):
    for c in candidates:
        if c in gdf.columns:
            return c
    # fall back: string column with the most unique values
    str_cols = [c for c in gdf.columns if gdf[c].dtype == object and c != "geometry"]
    if not str_cols:
        raise ValueError(f"No name column found; columns = {list(gdf.columns)}")
    return max(str_cols, key=lambda c: gdf[c].nunique())


def load_provinces(config) -> gpd.GeoDataFrame:
    """Province polygons with a normalized ``PROV_KEY`` column (WGS84)."""
    path = shapefile_path(config, config["geo"]["province_shapefile"])
    gdf = gpd.read_file(path)
    name_col = _detect_name_column(gdf)
    gdf = gdf.to_crs("EPSG:4326") if gdf.crs else gdf.set_crs("EPSG:4326")
    gdf["PROV_KEY"] = gdf[name_col].map(normalize_name)
    # shapefile-side fixes toward COMELC-era names
    gdf["PROV_KEY"] = gdf["PROV_KEY"].replace({
        "METROPOLITAN MANILA": NCR_CANONICAL,
        "METRO MANILA": NCR_CANONICAL,
        "NATIONAL CAPITAL REGION": NCR_CANONICAL,
        "SAMAR WESTERN SAMAR": "SAMAR",
        "WESTERN SAMAR": "SAMAR",
        "NORTH COTABATO": "COTABATO",
        "COTABATO NORTH COTABATO": "COTABATO",
        "SHARIFF KABUNSUAN": "MAGUINDANAO",
    })
    # dissolve duplicated keys (e.g. multi-part provinces)
    gdf = gdf[["PROV_KEY", "geometry"]].dissolve(by="PROV_KEY", as_index=False)
    return gdf


def load_municipalities(config) -> gpd.GeoDataFrame:
    """Municipal polygons with ``PROV_KEY``/``MUNI_KEY`` columns, or None if
    the (optional, downloaded) file is missing."""
    path = shapefile_path(config, config["geo"]["municipality_file"])
    if not Path(path).exists():
        return None
    gdf = gpd.read_file(path)
    if "PROV_KEY" not in gdf.columns or "MUNI_KEY" not in gdf.columns:
        # GADM naming: NAME_1 = province, NAME_2 = municipality
        prov_col = "NAME_1" if "NAME_1" in gdf.columns else _detect_name_column(gdf)
        muni_col = "NAME_2" if "NAME_2" in gdf.columns else _detect_name_column(gdf)
        gdf["PROV_KEY"] = gdf[prov_col].map(normalize_name)
        gdf["MUNI_KEY"] = gdf[muni_col].map(normalize_name)
    gdf = gdf.to_crs("EPSG:4326") if gdf.crs else gdf.set_crs("EPSG:4326")
    return gdf[["PROV_KEY", "MUNI_KEY", "geometry"]]


# ---------------------------------------------------------------------------
# Joining aggregated values onto geometries
# ---------------------------------------------------------------------------

MUNI_SUFFIXES = (" CITY", " CITY CAPITAL", " CAPITAL", " POB")

# COMELEC name -> GADM name (renames, GADM spellings/typos)
MUNI_ALIASES = {
    "CALOOCAN": "KALOOKAN",
    "CITY OF CALOOCAN": "KALOOKAN",
    "POZORRUBIO": "POZZORUBIO",          # GADM spelling
    "AMAI MANABILANG": "BUMBARAN",       # renamed 2018
    "OLD KAABAKAN": "KABACAN",
    "CITY OF BALIWAG": "BALIUAG",
    "SCIENCE CITY OF MUNOZ": "MUNOZ",
    "LEON T POSTIGO": "BACUNGAN",        # renamed 2000s
    "PIO V CORPUS": "PIO V CORPUZ",      # GADM spelling
    "ALBURQUERQUE": "ALBUQUERQUE",       # GADM spelling
    "GETAFE": "JETAFE",                  # GADM spelling
    "CORDOVA": "CORDOBA",                # GADM spelling
    "PINAMUNGAJAN": "PINAMUNGAHAN",      # GADM spelling
    "ISLAND GARDEN CITY OF SAMAL": "SAMAL",
}

# data province key (compact) does not always equal GADM NAME_1 (compact)
_GADM_PROV_FIXES = {
    "NORTHCOTABATO": "COTABATO",
}

# COMELEC abbreviations -> long forms used by GADM
_MUNI_WORD_EXPANSIONS = {
    "STA": "SANTA",
    "STO": "SANTO",
    "GEN": "GENERAL",
    "SGT": "SERGEANT",
    "PRES": "PRESIDENT",
    "MT": "MOUNT",
    "FT": "FORT",
}


def _muni_variants(name: str):
    """Normalized variants of a municipality/city name for fuzzy-ish matching."""
    n = normalize_name(name)
    # drop parentheticals (old names): "SAN JUAN (LAPOG)" -> "SAN JUAN"
    base = " ".join(re.sub(r"\(.*?\)", " ", str(name)).split())
    candidates = {n, normalize_name(base)}
    if n in MUNI_ALIASES:
        candidates.add(MUNI_ALIASES[n])
    _contractions = {v: k for k, v in _MUNI_WORD_EXPANSIONS.items()}
    for c in list(candidates):
        candidates.add(" ".join(_MUNI_WORD_EXPANSIONS.get(w, w) for w in c.split()))
        candidates.add(" ".join(_contractions.get(w, w) for w in c.split()))
    variants = []
    for c in candidates:
        variants.append(c)
        m = re.match(r"^CITY OF (.+)$", c)
        if m:
            variants += [m.group(1), f"{m.group(1)} CITY"]
        for suf in MUNI_SUFFIXES:
            if c.endswith(suf):
                variants.append(c[: -len(suf)].strip())
        if not c.endswith(" CITY"):
            variants.append(f"{c} CITY")
    return variants


def join_provinces(agg: pd.DataFrame, provinces: gpd.GeoDataFrame):
    """Merge a province-level aggregate onto province polygons.

    NCR districts and split/renamed provinces are collapsed into their
    canonical province (numeric values re-averaged weighted by precinct
    count, voter counts summed). Returns (gdf, unmatched_province_names).
    """
    agg = agg.copy()
    agg["PROV_KEY"] = [
        canonical_province(p, r) for p, r in zip(agg["PROVINCE"], agg["REGION"])
    ]
    merged = _weighted_regroup(agg, ["PROV_KEY"])
    # carry a region label for hover/dissolve (first observed)
    region_map = agg.groupby("PROV_KEY")["REGION"].first()
    merged["REGION"] = merged["PROV_KEY"].map(region_map)

    gdf = provinces.merge(merged, on="PROV_KEY", how="left")
    matched_keys = set(provinces["PROV_KEY"])
    unmatched = sorted(set(merged["PROV_KEY"]) - matched_keys)
    return gdf, unmatched


def join_regions(agg_prov: pd.DataFrame, provinces: gpd.GeoDataFrame, agg_region: pd.DataFrame):
    """Region-level map: dissolve province polygons by the data's own
    province→region assignment, then merge region-level values.

    agg_prov   : province-level aggregate (defines province→region).
    agg_region : region-level aggregate (values to display).
    """
    prov_gdf, unmatched = join_provinces(agg_prov, provinces)
    region_shapes = (
        prov_gdf.dropna(subset=["REGION"])[["REGION", "geometry"]]
        .dissolve(by="REGION", as_index=False)
    )
    gdf = region_shapes.merge(agg_region, on="REGION", how="left")
    return gdf, unmatched


def _weighted_regroup(df: pd.DataFrame, group_cols, weight_col: str = "n_precincts"):
    """Collapse rows sharing ``group_cols``: numeric columns are averaged
    weighted by ``weight_col``; precinct/voter count columns are summed."""
    sum_cols = [c for c in df.columns if c == "n_precincts" or c.startswith("information.")]
    num_cols = [c for c in df.select_dtypes("number").columns if c not in sum_cols]

    def _collapse(g):
        out = {}
        w = g[weight_col].to_numpy(dtype=float) if weight_col in g else np.ones(len(g))
        w_sum = w.sum() or 1.0
        for c in num_cols:
            out[c] = float((g[c].to_numpy() * w).sum() / w_sum)
        for c in sum_cols:
            out[c] = g[c].sum()
        return pd.Series(out)

    return df.groupby(group_cols, as_index=False, observed=True).apply(
        _collapse, include_groups=False
    )


def join_municipalities(agg: pd.DataFrame, municipalities: gpd.GeoDataFrame):
    """Merge a municipality-level aggregate onto municipal polygons.

    Matching is exact on (canonical province, municipality-name variant).
    COMELEC lists the City of Manila as its legislative districts
    (Tondo, Binondo, ...); these are dissolved into one MANILA row
    (precinct-weighted mean) before matching. Returns
    (gdf, match_rate, unmatched_dataframe).
    """
    muni = municipalities.copy()
    # compact keys throughout: GADM low-res names have no spaces
    lookup = {}
    for idx, row in muni.iterrows():
        prov = compact_key(row["PROV_KEY"])
        prov = _GADM_PROV_FIXES.get(prov, prov)
        lookup.setdefault((prov, compact_key(row["MUNI_KEY"])), idx)

    agg = agg.copy()
    agg["PROV_KEY"] = [
        canonical_province(p, r) for p, r in zip(agg["PROVINCE"], agg["REGION"])
    ]
    # Manila districts -> one city
    is_manila = agg["PROVINCE"].astype(str).str.upper().str.strip() == "NCR - MANILA"
    if is_manila.any():
        manila = _weighted_regroup(agg[is_manila], ["PROV_KEY"])
        manila["PROVINCE"] = "NCR - MANILA"
        manila["REGION"] = agg.loc[is_manila, "REGION"].iloc[0]
        manila["CITY_MUNICIPALITY"] = "MANILA"
        agg = pd.concat([agg[~is_manila], manila], ignore_index=True)

    match_idx = []
    for _, row in agg.iterrows():
        found = None
        prov = compact_key(row["PROV_KEY"])
        for var in _muni_variants(row["CITY_MUNICIPALITY"]):
            found = lookup.get((prov, compact_key(var)))
            if found is not None:
                break
        match_idx.append(found)
    agg["_geom_idx"] = match_idx

    matched = agg.dropna(subset=["_geom_idx"]).copy()
    matched["_geom_idx"] = matched["_geom_idx"].astype(int)
    gdf = gpd.GeoDataFrame(
        matched.drop(columns=["_geom_idx"]),
        geometry=muni.loc[matched["_geom_idx"], "geometry"].values,
        crs=muni.crs,
    )
    unmatched = agg[agg["_geom_idx"].isna()].drop(columns=["_geom_idx"])
    rate = len(matched) / len(agg) if len(agg) else 0.0
    return gdf, rate, unmatched
