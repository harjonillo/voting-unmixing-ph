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

from app.components import theme
from app.components.data import AVAILABLE_YEARS, build_view, get_processed
from app.components.sidebar import render_sidebar, select_year
from app.tabs import comparison, distributions, overview, table

st.set_page_config(page_title="PH voting archetypes", layout="wide")
theme.register_template()

year = select_year(AVAILABLE_YEARS)

try:
    endmembers, abundances, meta = get_processed(year)
except FileNotFoundError:
    st.error(
        f"Processed artifacts for {year} not found. Run "
        f"`python scripts/run_pipeline.py --config configs/config_{year}.ini` "
        "from the repo root first (see README)."
    )
    st.stop()

controls = render_sidebar(abundances, list(endmembers.columns), meta, year)
view = build_view(endmembers, abundances, meta, controls)

tab_map, tab_compare, tab_dist = st.tabs(
    ["Map / overview", "Model comparison", "Abundance distributions"]
)

with tab_map:
    overview.render(view)

with tab_compare:
    comparison.render(view)

with tab_dist:
    distributions.render(view)

