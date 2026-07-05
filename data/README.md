# Data provenance

Everything in this folder is **gitignored** (except this README). Rebuild it as follows.

## Copied from `../2025-PH-elections/data/`

| file | description |
|---|---|
| `2025_senators_complete.csv` | Per clustered precinct: geography, turnout stats, votes per senatorial candidate (2025 NLE). |
| `2025_senators_filtered.csv` | Same, filtered version used by older notebooks. |
| `2025_clustered_precincts_*.txt` | Precinct ID lists (all / local / overseas). |
| `results_hannahtest/` | MATLAB unmixing outputs (N-FINDR pre-estimate spectra + coefficients), kept for cross-checking. |

## Copied from `BSthesis-main-2` (previous advisee's shapefiles)

- `shapefiles/regions/Regions.shp` (+ sidecars)
- `shapefiles/provinces/Provinces.shp` (+ sidecars)

## Downloaded

- `shapefiles/municipalities.geojson` — municipal/city boundaries
  (see `scripts/fetch_boundaries.py`; optional, the app falls back to
  region/province maps if this file is missing).

## Generated

- `processed/` — outputs of `scripts/run_pipeline.py`
  (`endmembers.csv`, `abundances.parquet`, `meta.json`). The Streamlit app
  reads only these + the shapefiles.
