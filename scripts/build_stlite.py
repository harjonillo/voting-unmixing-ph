"""Assemble a static stlite site for GitHub Pages.

stlite runs Streamlit fully in the browser (Pyodide/WebAssembly), so the whole
app plus the data files it reads are shipped as static assets. This script
builds a ``dist/`` directory containing:

  - index.html   boots stlite, inlines the Python source, and points the data
                 files at URLs served alongside it.
  - data/...     copies of only the files the app actually reads.

The Python modules (app/, src/, configs/config.ini) are small, so they are
inlined into index.html as text. The data files are large, so they are copied
next to index.html and fetched at runtime by stlite via ``{ url: ... }``.

Path invariant: every virtual file key is RELATIVE (``app/...``, ``src/...``,
``configs/...``, ``data/...``). stlite mounts them under one root, and
``src/config.py`` derives REPO_ROOT as ``__file__.parent.parent``; keeping keys
relative makes the in-browser absolute paths line up with the repo layout.

Run from the repo root:
    python scripts/build_stlite.py --out dist
"""

import argparse
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# stlite bundles Streamlit itself, so it is NOT listed here. numpy/pandas come
# in as transitive dependencies of the packages below.
REQUIREMENTS = [
    "geopandas",
    "pyarrow",
    "plotly",
    "matplotlib",
    "seaborn",
    "scikit-learn",
    "scipy",
    # pulled in eagerly by src/unmixing/__init__.py (endmember_extraction)
    "tqdm",
]

ENTRYPOINT = "app/streamlit_app.py"

# Python/text trees inlined into index.html. __pycache__ is skipped.
TEXT_DIRS = ["app", "src"]
TEXT_FILES = ["configs/config_2019.ini", "configs/config_2022.ini", "configs/config_2025.ini"]

# The ONLY data files the app reads (traced through app/components/data.py:
# load_processed, load_provinces, load_municipalities, load_sweep). Notably it
# does NOT read the sweep abundances_ref.parquet, the regions/ shapefile, or the
# gadm zip. Shapefiles need their whole sidecar set (.shx/.dbf/.prj/...).
DATA_FILES = [
    # boundaries
    "data/shapefiles/municipalities.geojson",
    "data/shapefiles/provinces/Provinces.shp",
    "data/shapefiles/provinces/Provinces.shx",
    "data/shapefiles/provinces/Provinces.dbf",
    "data/shapefiles/provinces/Provinces.prj",
    "data/shapefiles/provinces/Provinces.sbn",
    "data/shapefiles/provinces/Provinces.sbx",
    "data/shapefiles/provinces/Provinces.shp.xml",
]

for year in ["2019", "2022", "2025"]:
    DATA_FILES += [
        # processed pipeline outputs
        f"data/processed/{year}/endmembers.csv",
        f"data/processed/{year}/abundances.parquet",
        f"data/processed/{year}/meta.json",
    ]
    # endmember-count sweep (per p: everything except the heavy abundances_ref)
    for _p in range(2, 8):
        DATA_FILES += [
            f"data/processed/{year}/sweep/p{_p}/loadings_mean.csv",
            f"data/processed/{year}/sweep/p{_p}/loadings_std.csv",
            f"data/processed/{year}/sweep/p{_p}/agg_municipality_trials.parquet",
            f"data/processed/{year}/sweep/p{_p}/meta.json",
        ]


def collect_text_files() -> dict[str, str]:
    """Map of relative path -> file contents for the inlined Python/config."""
    files: dict[str, str] = {}
    for d in TEXT_DIRS:
        for path in sorted((REPO_ROOT / d).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            files[rel] = path.read_text(encoding="utf-8")
    for f in TEXT_FILES:
        files[f] = (REPO_ROOT / f).read_text(encoding="utf-8")
    return files


def copy_data(out: Path) -> int:
    """Copy the needed data files into ``out`` preserving structure. Returns bytes."""
    total = 0
    for rel in DATA_FILES:
        src = REPO_ROOT / rel
        if not src.exists():
            raise FileNotFoundError(
                f"Required data file missing: {rel}\n"
                "It must be committed for the app to work "
                "(see the data un-ignore rules in .gitignore)."
            )
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total += src.stat().st_size
    return total


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PH voting archetypes</title>
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/@stlite/browser@1.8.1/build/stlite.css"
    />
    <style>
      html, body {{ margin: 0; padding: 0; }}
      #root {{ height: 100vh; }}
      #boot {{ font-family: sans-serif; padding: 2rem; color: #444; }}
    </style>
  </head>
  <body>
    <div id="root"><div id="boot">Loading the app (first load fetches Python
      packages and ~36&nbsp;MB of data; this can take a minute)&hellip;</div></div>

    <script type="application/json" id="py-files">{py_files}</script>
    <script type="application/json" id="data-files">{data_files}</script>
    <script type="application/json" id="requirements">{requirements}</script>

    <script type="module">
      import {{ mount }} from
        "https://cdn.jsdelivr.net/npm/@stlite/browser@1.8.1/build/stlite.js";

      const text = JSON.parse(document.getElementById("py-files").textContent);
      const dataList = JSON.parse(document.getElementById("data-files").textContent);
      const requirements = JSON.parse(document.getElementById("requirements").textContent);

      const files = {{ ...text }};
      // Large assets are fetched at runtime from the same host as this page.
      // Relative URLs work whether served at the user root (harjonillo.github.io)
      // or a project path (harjonillo.github.io/voting-unmixing-ph/).
      for (const p of dataList) files[p] = {{ url: "./" + p }};

      mount(
        {{
          requirements,
          entrypoint: {entrypoint},
          files,
          streamlitConfig: {{ "client.toolbarMode": "minimal" }},
        }},
        document.getElementById("root"),
      );
    </script>
  </body>
</html>
"""


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    text_files = collect_text_files()
    data_bytes = copy_data(out)

    index = INDEX_TEMPLATE.format(
        py_files=json.dumps(text_files),
        data_files=json.dumps(DATA_FILES),
        requirements=json.dumps(REQUIREMENTS),
        entrypoint=json.dumps(ENTRYPOINT),
    )
    (out / "index.html").write_text(index, encoding="utf-8")
    # Tell Pages not to run Jekyll (which would ignore some files).
    (out / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Wrote {out}/index.html")
    print(f"Inlined {len(text_files)} Python/config files")
    print(f"Copied {len(DATA_FILES)} data files ({data_bytes / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    args = ap.parse_args()
    build((REPO_ROOT / args.out).resolve() if not Path(args.out).is_absolute()
          else Path(args.out))


if __name__ == "__main__":
    main()
