"""Render the static FastHTML shell for the voting-archetype explorer.

FastHTML is used here purely as an HTML generator: it builds the page's
component tree in Python and serializes it to a single ``index.html``. The page
is inert on its own — all interactivity is client-side (web/app.js + Plotly.js),
re-slicing the JSON that scripts/build_static.py bakes into ``site/data/``.

Styling is Tailwind CSS (Play CDN) + daisyUI (component classes + themes). Swap
the whole palette by changing the ``data-theme`` on <html> below to any daisyUI
theme name ("corporate", "light", "emerald", "business", ...). web/styles.css
holds only the few app-specific rules on top.

This writes into the same output dir as build_static.py (default ``site``):

    site/index.html     the shell (this script)
    site/styles.css     copied from web/styles.css
    site/app.js         copied from web/app.js
    site/data/...        the baked dataset (build_static.py — run that first)

Run from the repo root:
    python scripts/build_static.py --out site/data   # data (once / on data change)
    python scripts/build_site.py   --out site        # this shell
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from fasthtml.common import (
    Aside, Body, Button, Div, H2, Head, Html, Input, Label, Link, Main,
    Meta, Nav, Option, P, Script, Section, Select, Span, Title, to_xml,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB = REPO_ROOT / "web"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"
TAILWIND_CDN = "https://cdn.tailwindcss.com"
DAISYUI_CDN = "https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css"
DAISY_THEME = "light"  # any daisyUI theme name (light = the daisyUI-site default)

# Shared class strings (keep the markup below readable).
SELECT = "select select-bordered select-sm"
INPUT = "input input-bordered input-sm"
CARD = "card bg-base-100 shadow-md border border-base-200"


def field(label_text: str, control) -> Div:
    """A sidebar (label above control) block."""
    return Div(Label(label_text, cls="block text-sm font-medium mb-1"), control, cls="mb-4")


def labeled(label_text: str, control) -> Div:
    """A compact (tiny label above control) cell for the inline control strips."""
    return Div(Span(label_text, cls="text-xs opacity-60"), control, cls="flex flex-col gap-1")


def card(*content, span: str = "") -> Div:
    """A daisyUI card wrapping plot content; `span` adds a grid col-span class."""
    return Div(Div(*content, cls="card-body p-4"), cls=f"{CARD} {span}".strip())


def sidebar() -> Aside:
    return Aside(
        P("Spectral-unmixing explorer of PH senatorial votes.", cls="text-xs opacity-60 mb-1"),
        P(id="sidebar-caption", cls="text-xs opacity-60 mb-4"),
        field("Election year", Select(id="year", cls=f"{SELECT} w-full")),
        Div(
            Label("Aggregation level", cls="block text-sm font-medium mb-1"),
            Div(id="levels", cls="space-y-1"),
            cls="mb-4",
        ),
        field("Top N candidates",
              Input(type="number", id="topN", min=3, max=15, value=5, step=1, cls=f"{INPUT} w-full")),
        Div(
            Label(
                Input(type="checkbox", id="weighted", checked=True, cls="checkbox checkbox-sm"),
                Span("Weight means by valid ballots", cls="text-sm"),
                cls="flex items-center gap-2 cursor-pointer",
            ),
            cls="mb-4",
        ),
        cls="w-72 shrink-0 bg-base-100 border-r border-base-300 p-4 min-h-screen",
    )


def tab_map() -> Section:
    return Section(
        H2("Geographic distribution of archetypes", cls="text-base font-semibold mb-2"),
        Div(
            labeled("Quantity", Select(id="map-quantity", cls=SELECT)),
            labeled("Archetype", Select(id="map-arch", cls=SELECT)),
            cls="flex flex-wrap gap-3 items-end mb-3",
        ),
        # map : loadings in a 2:3 ratio — the Tailwind way to do st.columns([2, 3]).
        Div(
            card(Div(id="map-plot"), span="lg:col-span-2"),
            card(Div(id="map-loadings"), span="lg:col-span-3"),
            cls="grid grid-cols-1 lg:grid-cols-5 gap-4",
        ),
        id="tab-map",
    )


def tab_compare() -> Section:
    return Section(
        H2("Endmember-count comparison", cls="text-base font-semibold mb-2"),
        P("Trial mean/std at a chosen archetype count p (precomputed by the sweep). "
          "The map follows the sidebar level and weighting.", cls="text-sm opacity-60 mb-3"),
        card(
            H2("Archetype lineage", cls="text-sm font-semibold mb-1"),
            P("How archetypes split as the endmember count p grows (2 → 3 → "
              "…). Consecutive p are cosine-matched; a highlighted link marks the "
              "archetype that splits off when p increases by one. Each node is labelled "
              "with its top-loading candidate; ribbon width ≈ match similarity.",
              cls="text-sm opacity-60 mb-2"),
            Div(id="cmp-lineage"),
            span="mb-4",
        ),
        # Controls below drive the succeeding per-p map and loadings, not the
        # sweep-wide lineage above.
        Div(
            labeled("Archetypes p", Select(id="cmp-p", cls=SELECT)),
            labeled("Archetype", Select(id="cmp-arch", cls=SELECT)),
            labeled("Map shows", Select(
                Option("Mean abundance", value="mean"),
                Option("Std across trials", value="std"),
                id="cmp-stat", cls=SELECT,
            )),
            labeled("Top N candidates",
                    Input(type="number", id="cmp-topN", min=5, max=40, value=15, step=1, cls=f"{INPUT} w-28")),
            cls="flex flex-wrap gap-3 items-end mb-3",
        ),
        Div(card(Div(id="cmp-plot")), card(Div(id="cmp-loadings")), cls="grid gap-4"),
        id="tab-compare", hidden=True,
    )


def tab_dist() -> Section:
    return Section(
        H2("Abundance distributions", cls="text-base font-semibold mb-2"),
        P("Distribution of each archetype's abundance across the units at the current "
          "aggregation level.", cls="text-sm opacity-60 mb-3"),
        card(Div(id="dist-plots")),
        id="tab-dist", hidden=True,
    )


def page() -> Html:
    return Html(
        Head(
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Title("PH voting archetypes"),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin="anonymous"),
            Link(rel="stylesheet",
                 href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap"),
            Link(rel="stylesheet", href=DAISYUI_CDN),
            Script(src=TAILWIND_CDN),
            Link(rel="stylesheet", href="./styles.css"),  # our overrides, after Tailwind/daisyUI
            Script(src=PLOTLY_CDN),
        ),
        Body(
            Div(
                Span("PH Voting Archetypes", cls="text-lg font-semibold"),
                cls="navbar bg-base-100 border-b border-base-300 px-4 min-h-0 py-2",
            ),
            Div(
                sidebar(),
                Main(
                    Div(
                        Nav(
                            Button("Map / overview", id="tabbtn-map", cls="tab tab-active"),
                            Button("Model comparison", id="tabbtn-compare", cls="tab"),
                            Button("Abundance distributions", id="tabbtn-dist", cls="tab"),
                            role="tablist", cls="tabs tabs-bordered",
                        ),
                        Span(id="status", cls="text-xs opacity-60 ml-2"),
                        cls="flex items-center gap-2 mb-4",
                    ),
                    tab_map(),
                    tab_compare(),
                    tab_dist(),
                    cls="flex-1 min-w-0 p-6",
                ),
                cls="flex",
            ),
            Script(src="./app.js"),
            cls="min-h-screen bg-base-100",
        ),
        lang="en", data_theme=DAISY_THEME,
    )


def build(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    html = to_xml(page())
    if not html.lstrip().lower().startswith("<!doctype"):
        html = "<!doctype html>\n" + html
    (out / "index.html").write_text(html, encoding="utf-8")
    for asset in ("styles.css", "app.js"):
        shutil.copy2(WEB / asset, out / asset)
    data = out / "data"
    note = "" if (data / "manifest.json").exists() else \
        "  (!) site/data is empty — run scripts/build_static.py --out site/data first"
    print(f"Wrote {out}/index.html + styles.css + app.js{note}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="site", help="output dir (default: site)")
    args = ap.parse_args()
    target = Path(args.out)
    build(target if target.is_absolute() else (REPO_ROOT / target).resolve())


if __name__ == "__main__":
    main()
