"""Render the static FastHTML shell for the voting-archetype explorer.

FastHTML is used here purely as an HTML generator: it builds the page's
component tree in Python and serializes it to a single ``index.html``. The page
is inert on its own — all interactivity is client-side (web/app.js + Plotly.js),
re-slicing the JSON that scripts/build_static.py bakes into ``site/data/``.

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
    Body, Button, Div, H1, H2, Head, Html, Input, Label, Link, Main,
    Meta, Option, P, Script, Section, Select, Span, Title, Aside, Nav, to_xml,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB = REPO_ROOT / "web"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"


def labeled(label_text: str, control) -> Div:
    """A stacked (label, control) pair for the inline control rows."""
    return Div(Span(label_text), control, cls="ctrl")


def sidebar() -> Aside:
    return Aside(
        H1("PH voting archetypes"),
        P("Spectral-unmixing explorer of PH senatorial votes.", cls="muted"),
        P(id="sidebar-caption", cls="muted"),
        Div(
            Label("Election year", cls="block"),
            Select(id="year"),
            cls="field",
        ),
        Div(
            Label("Aggregation level", cls="block"),
            Div(id="levels"),
            cls="field",
        ),
        Div(
            Label("Top N candidates", cls="block"),
            Input(type="number", id="topN", min=3, max=15, value=5, step=1),
            cls="field",
        ),
        Div(
            Label(
                Input(type="checkbox", id="weighted", checked=True),
                " Weight means by valid ballots",
                cls="checkbox",
            ),
            cls="field",
        ),
        cls="sidebar",
    )


def tab_map() -> Section:
    return Section(
        H2("Geographic distribution of archetypes"),
        Div(
            labeled("Quantity", Select(id="map-quantity")),
            labeled("Archetype", Select(id="map-arch")),
            cls="controls",
        ),
        Div(
            Div(id="map-plot"),
            Div(id="map-loadings"),
            cls="split",
        ),
        id="tab-map",
    )


def tab_compare() -> Section:
    return Section(
        H2("Endmember-count comparison"),
        P(
            "Trial mean/std at a chosen archetype count p (precomputed by the "
            "sweep). The map follows the sidebar level and weighting.",
            cls="muted",
        ),
        Div(
            labeled("Archetypes p", Select(id="cmp-p")),
            labeled("Archetype", Select(id="cmp-arch")),
            labeled(
                "Map shows",
                Select(
                    Option("Mean abundance", value="mean"),
                    Option("Std across trials", value="std"),
                    id="cmp-stat",
                ),
            ),
            labeled("Top N candidates", Input(type="number", id="cmp-topN",
                                              min=5, max=40, value=15, step=1)),
            cls="controls",
        ),
        Div(id="cmp-plot"),
        Div(id="cmp-loadings"),
        id="tab-compare", hidden=True,
    )


def tab_dist() -> Section:
    return Section(
        H2("Abundance distributions"),
        P("Distribution of each archetype's abundance across the units at the "
          "current aggregation level.", cls="muted"),
        Div(id="dist-plots"),
        id="tab-dist", hidden=True,
    )


def page() -> Html:
    return Html(
        Head(
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Title("PH voting archetypes"),
            Link(rel="stylesheet", href="./styles.css"),
            Script(src=PLOTLY_CDN),
        ),
        Body(
            Div(
                sidebar(),
                Main(
                    Nav(
                        Button("Map / overview", id="tabbtn-map", cls="active"),
                        Button("Model comparison", id="tabbtn-compare"),
                        Button("Abundance distributions", id="tabbtn-dist"),
                        Span(id="status"),
                        cls="tabs",
                    ),
                    tab_map(),
                    tab_compare(),
                    tab_dist(),
                ),
                cls="app",
            ),
            Script(src="./app.js"),
        ),
        lang="en",
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
