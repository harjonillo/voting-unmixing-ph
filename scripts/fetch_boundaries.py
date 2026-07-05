"""Download PH municipal/city boundaries (GADM 4.1 level 2), simplify them,
and save data/shapefiles/municipalities.geojson with PROV_KEY/MUNI_KEY columns.

Optional: the app falls back to region/province maps if this file is missing.

Run from the repo root:
    python scripts/fetch_boundaries.py
"""

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd

from src.config import load_config, shapefile_path
from src.geo import normalize_name

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PHL_2.json.zip"
SIMPLIFY_TOLERANCE = 0.002  # degrees; keeps the app responsive


def main():
    config = load_config()
    out = shapefile_path(config, config["geo"]["municipality_file"])
    out.parent.mkdir(parents=True, exist_ok=True)

    cached = out.parent / "gadm41_PHL_2.json.zip"
    if cached.exists():
        print(f"using cached {cached}")
        payload = cached.read_bytes()
    else:
        print(f"downloading {GADM_URL} ...")
        with urllib.request.urlopen(GADM_URL, timeout=300) as resp:
            payload = resp.read()
    print(f"  {len(payload) / 1e6:.1f} MB")

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        inner = zf.namelist()[0]
        with zf.open(inner) as f:
            gdf = gpd.read_file(f)

    print(f"features: {len(gdf)}")
    gdf["PROV_KEY"] = gdf["NAME_1"].map(normalize_name)
    gdf["MUNI_KEY"] = gdf["NAME_2"].map(normalize_name)
    gdf = gdf[["PROV_KEY", "MUNI_KEY", "geometry"]]
    gdf = gdf.set_geometry(gdf.geometry.simplify(SIMPLIFY_TOLERANCE))
    gdf.to_file(out, driver="GeoJSON")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
