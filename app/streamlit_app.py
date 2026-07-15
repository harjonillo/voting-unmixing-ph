"""Voting-archetype explorer.

Reads the artifacts written by scripts/run_pipeline.py (data/processed/) and
the shapefiles in data/shapefiles/, and shows archetype abundances and
endmember loadings at a chosen aggregation level.

The sidebar selections (app/components/sidebar.py) drive a View
(app/components/data.py) that each tab in app/tabs/ renders.

Run from the repo root:
    streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

from app.components.data import build_view, get_processed
from app.components.sidebar import render_sidebar
from app.tabs import comparison, distributions, loadings, overview, table

st.set_page_config(page_title="PH voting archetypes", layout="wide")

try:
    endmembers, abundances, meta = get_processed()
except FileNotFoundError:
    st.error(
        "Processed artifacts not found. Run `python scripts/run_pipeline.py` "
        "from the repo root first (see README)."
    )
    st.stop()

controls = render_sidebar(abundances, list(endmembers.columns), meta)
view = build_view(endmembers, abundances, meta, controls)

tab_map, tab_loadings, tab_dist, tab_table, tab_compare = st.tabs(
    ["Map / overview", "Endmember loadings", "Abundance distributions", "Table",
     "Model comparison"]
)

with tab_map:
    overview.render(view)

with tab_loadings:
    loadings.render(view)

with tab_dist:
    distributions.render(view)

with tab_table:
    table.render(view)

with tab_compare:
    comparison.render()
