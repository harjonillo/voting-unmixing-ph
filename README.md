# voting-unmixing-ph

Spectral-unmixing analysis of Philippine election results: voting archetypes
(endmembers) and their per-precinct abundances, with maps and plots at
national / region / province / municipality / clustered-precinct level.

Cleaned-up successor to the exploratory `2025-PH-elections` notebooks and the
curated `voting-archetypes-ph` modules.

## Layout

```
configs/config.ini      paths + preprocessing/unmixing parameters
data/                   gitignored — see data/README.md for provenance
src/
  config.py             config + path helpers
  data/                 loading.py (CSV/MATLAB/processed IO), preprocessing.py
  unmixing/             VCA, N-FINDR, MVSA, SUNSAL, HySime, noise, matching, tools
  aggregation.py        precinct -> region/province/municipality aggregation
  geo.py                shapefile loading + COMELEC<->shapefile name matching
  figures/              archetype/abundance plots + choropleth helpers
scripts/
  run_pipeline.py       CSV -> HySime -> MVSA -> SUNSAL -> data/processed/
  run_sweep.py          multi-trial sweep over p = p_min..p_max (error bars,
                        stability, lineage) -> data/processed/sweep/p{p}/
  fetch_boundaries.py   downloads municipal boundaries (GADM, optional)
notebooks/              demo notebooks (how to make each kind of plot)
app/
  streamlit_app.py      interactive explorer: loads artifacts, draws the tabs
  components/           sidebar controls, cached loading + derived View,
                        shared chart/map builders
  tabs/                 one module per tab (overview, loadings,
                        distributions, table, comparison)
```

## Setup

```bash
conda activate voting_unmixing_ph_env   # created with:
# conda create -n voting_unmixing_ph_env -c conda-forge python=3.13 \
#   numpy scipy pandas matplotlib seaborn geopandas streamlit plotly \
#   jupyter ipykernel openpyxl pyarrow scikit-learn
```

Populate `data/` (see `data/README.md`), then from the repo root:

```bash
python scripts/fetch_boundaries.py   # optional: municipal-level maps
python scripts/run_pipeline.py       # writes data/processed/
python scripts/run_sweep.py          # ~5 min: powers the Model-comparison tab
streamlit run app/streamlit_app.py
```

## Web deployment

Because the app does no on-demand computation — the heavy unmixing is
precomputed by `run_pipeline.py`/`run_sweep.py`, and the app only aggregates,
matches and draws — it can be served as a **fully static** site.

`scripts/build_static.py` pre-computes every selection (year × level ×
weighting, endmember loadings, and the per-p sweep detail) into JSON +
simplified GeoJSON under `site/data/`; `scripts/build_site.py` renders the page
shell (`site/index.html`) with [FastHTML](https://fastht.ml) + Tailwind/daisyUI.
The browser loads only the files for the current view and draws them with
Plotly.js — **no server and no Pyodide**, so a first visit pulls ~½ MB.
`.github/workflows/deploy-static.yml` builds and publishes `site/` to GitHub
Pages on every push to `main` (set **Settings → Pages → Source = "GitHub
Actions"** once). Published at `harjonillo.github.io/voting-unmixing-ph/`.

Build and test locally (needs the conda env below plus `python-fasthtml`):

```bash
pip install python-fasthtml                       # once, into the env
python scripts/build_static.py --out site/data --verify   # bake JSON + GeoJSON (--verify checks parity with the app)
python scripts/build_site.py   --out site                 # render the FastHTML shell
cd site && python -m http.server 8000             # open http://localhost:8000 (needs internet for the Plotly/Tailwind CDNs)
```

Rebuild `site/data` whenever the pipeline/sweep outputs change; rebuild the
shell whenever `web/app.js`, `web/styles.css`, or `scripts/build_site.py`
change. `site/` is generated (gitignored) and rebuilt in CI from the committed
`data/processed/` + `data/shapefiles/` trees.

For a fully dynamic host instead, the Streamlit app runs directly:
`pip install -r requirements.txt && streamlit run app/streamlit_app.py`.

## Notebooks

| notebook | shows |
|---|---|
| `01_data_overview` | loading, filtering, turnout/vote distributions |
| `02_unmixing_pipeline` | noise estimation, HySime, MVSA, SUNSAL, diagnostics |
| `03_archetype_plots` | endmember loadings, abundance panels, reconstruction, noise floor |
| `04_maps` | choropleths at each aggregation level |
| `05_model_comparison` | RMSE/stability vs p, archetype lineage, loadings ± std over trials |

## Notes

- Region maps are built by dissolving the **province** shapefile with the
  data's own province→region assignment, so post-2024 regions (BARMM, NIR)
  render correctly despite the older shapefiles.
- Normalization of the vote matrix is configurable
  (`[preprocessing] normalization`): `valid_ballots` (default), `row_max`, `none`.
- MATLAB results (`results_hannahtest/`) are loadable via
  `src.data.load_matlab_results` for comparison, but their row alignment with
  the CSVs is not guaranteed — the app uses only the Python pipeline outputs.
