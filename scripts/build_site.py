"""Render the static FastHTML shell for the voting-archetype explorer.

FastHTML is used here purely as an HTML generator: it builds the page's
component tree in Python and serializes it to a single ``index.html``. The page
is inert on its own — all interactivity is client-side (web/app.js + Plotly.js),
re-slicing the JSON that scripts/build_static.py bakes into ``site/data/``.

Styling is plain CSS in web/styles.css (design tokens as CSS variables; see
docs/redesign/README.md). The markup below only names its classes. UI chrome is
black and gray; color is reserved for data.

This writes into the same output dir as build_static.py (default ``site``):

    site/index.html     the shell (this script)
    site/styles.css     copied from web/styles.css
    site/app.js         copied from web/app.js
    site/data/...        the baked dataset (build_static.py — run that first)

Run from the repo root:
    python scripts/bake_distinctness.py              # prerequisites of build_static
    python scripts/bake_order_sensitivity.py         #   (see its docstring)
    python scripts/build_static.py --out site/data   # data (once / on data change)
    python scripts/build_site.py   --out site        # this shell
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from fasthtml.common import (
    A,
    Aside,
    Body,
    Button,
    Div,
    Fieldset,
    Figcaption,
    Figure,
    H1,
    H2,
    H3,
    Head,
    Header,
    Html,
    Input,
    Label,
    Legend,
    Link,
    Main,
    Meta,
    Nav,
    Option,
    P,
    Script,
    Section,
    Select,
    Span,
    Title,
    to_xml,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB = REPO_ROOT / "web"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"
FONTS_CSS = (
    "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500&display=swap"
)
REPO_URL = "https://github.com/harjonillo/voting-unmixing-ph"
PROJECT_LINKS = [
    ("Method notes", f"{REPO_URL}#readme"),
    ("Data sources", f"{REPO_URL}/blob/main/data/README.md"),
    ("GitHub", REPO_URL),
]


def seg_group(group_id: str, label: str, options=(), fill: bool = False) -> Div:
    """A segmented control: buttons in a gray track, one pressed at a time.
    `options` are (value, text) pairs; leave empty for app.js to fill. app.js
    wires the clicks and sets aria-pressed / .on."""
    return Div(
        *(
            Button(text, type="button", cls="seg", data_value=value, aria_pressed="false")
            for value, text in options
        ),
        id=group_id,
        role="group",
        aria_label=label,
        cls="seg-group fill" if fill else "seg-group",
    )


def field(label_text: str, control, note: str | None = None) -> Div:
    """A sidebar block: label above control, optional caption below."""
    return Div(
        Span(label_text, cls="field-label"),
        control,
        Span(note, cls="note") if note else None,
        cls="field",
    )


def labeled(label_text: str, control) -> Div:
    """A compact (small label above control) cell for the inline control strips."""
    return Div(Span(label_text, cls="note"), control, cls="labeled")


def card(*content, cls: str = "") -> Div:
    return Div(*content, cls=f"card {cls}".strip())


def card_head(title: str, sub: str | None = None, *controls, sub_id=None) -> Div:
    """Card title + caption on the left, optional controls on the right."""
    return Div(
        Div(
            H3(title, cls="card-title"),
            P(sub, id=sub_id, cls="card-sub") if (sub or sub_id) else None,
            cls="card-head-text",
        ),
        *controls,
        cls="card-head",
    )


def sidebar() -> Aside:
    return Aside(
        Section(
            H2("Data", cls="overline"),
            field("Election year", seg_group("year", "Election year")),
            Fieldset(
                Legend("Aggregation level", cls="field-label"),
                Div(id="levels", cls="radios"),
                cls="field",
            ),
            Label(
                Input(type="checkbox", id="weighted", checked=True),
                "Weight means by valid ballots",
                cls="check",
            ),
            cls="side-group",
        ),
        Section(
            H2("Model", cls="overline"),
            # Options come from the manifest's "methods" (MVSA / NMF); every tab
            # reads that method's baked tree. Abundances are SUNSAL either way.
            field(
                "Endmember extraction",
                seg_group("method", "Endmember extraction", fill=True),
                note="Abundances are SUNSAL for both",
            ),
            Div(
                Label("Top N candidates", fr="topN", cls="field-label"),
                Div(
                    Button("−", type="button", id="topN-dec", cls="step", aria_label="Fewer"),
                    Input(type="number", id="topN", min=3, max=15, value=6, step=1),
                    Button("+", type="button", id="topN-inc", cls="step", aria_label="More"),
                    cls="stepper",
                ),
                cls="field",
            ),
            cls="side-group",
        ),
        # Run summary for the selected year + method (filled from the manifest).
        Section(id="run-summary", cls="side-group summary"),
        cls="sidebar",
    )


def tab_map() -> Section:
    return Section(
        Div(
            H2("Geographic distribution of archetypes", cls="section-title"),
            P(id="map-lede", cls="lede"),
            cls="section-head",
        ),
        Div(
            seg_group("map-quantity", "Quantity"),
            Div(id="map-arch", role="group", aria_label="Archetype", cls="chips"),
            cls="toolbar",
        ),
        # map : loadings at 3fr : 2fr (the map gets the larger share).
        Div(
            Figure(
                Figcaption(
                    Span(id="map-title", cls="card-title"),
                    Span(id="map-subtitle", cls="note"),
                    cls="fig-head",
                ),
                Div(id="map-plot"),
                Div(
                    Div(
                        Span("Color range", cls="field-label"),
                        seg_group(
                            "map-range",
                            "Color range",
                            [("data", "Data range"), ("fixed", "Fixed 0 to 1")],
                        ),
                        id="map-range-row",
                        cls="legend-row",
                    ),
                    Div(id="map-legend"),
                    P(id="map-legend-note", cls="note"),
                    cls="map-foot",
                ),
                cls="card",
            ),
            card(
                card_head(
                    "Candidate weights per endmember",
                    None,
                    Div(
                        Span("X-axis", cls="note"),
                        seg_group(
                            "map-axis",
                            "X-axis scaling",
                            [("shared", "Shared"), ("own", "Per archetype")],
                        ),
                        cls="head-control",
                    ),
                    sub_id="map-loadings-sub",
                ),
                Div(id="map-loadings"),
            ),
            cls="grid-32",
        ),
        Div(
            card(
                card_head(
                    "Party / alliance mixing",
                    None,
                    seg_group(
                        "map-groupby",
                        "Group by",
                        [("party", "Party"), ("alliance", "Alliance")],
                    ),
                    sub_id="map-partylist-sub",
                ),
                Div(id="map-partylist"),
            ),
            card(
                card_head("Candidates", None, sub_id="map-partylist-table-sub"),
                Div(id="map-partylist-table"),
            ),
            cls="grid-32",
        ),
        id="tab-map",
        cls="tab-panel",
    )


def tab_compare() -> Section:
    return Section(
        Div(
            H2("Endmember-count comparison", cls="section-title"),
            P(
                "Trial mean / 1 SD at a chosen archetype count p (precomputed by the "
                "sweep). The map follows the sidebar level and weighting.",
                cls="lede",
            ),
            cls="section-head",
        ),
        card(
            card_head(
                "Archetype lineage",
                "Network of archetypes across the sweep, one column per endmember "
                "count p. Each node lists an archetype's top candidates; edge width "
                "and label show the chosen similarity metric between the two loading "
                "columns. Solid links are the Hungarian match from p to p+1 "
                "(including the extra archetype's link to its closest parent — "
                "hover says which), and faint links are other similar-enough pairs. "
                "Above each column: the min/mean pairwise distance between that p's "
                "archetypes (0 = identical, 1 = distinct) — where the min collapses, "
                "the newest archetype duplicates an existing one.",
                Div(
                    labeled(
                        "Similarity metric",
                        Select(
                            Option("Cosine (top 12)", value="cos12"),
                            Option("Cosine (full)", value="cos"),
                            Option("Spearman r", value="spearman"),
                            Option("Weighted tau", value="wtau"),
                            Option("RBO", value="rbo"),
                            Option("Jaccard (top 12)", value="jac12"),
                            id="cmp-lineage-metric",
                        ),
                    ),
                    labeled(
                        "Column distance",
                        Select(
                            Option("Min pairwise", value="min"),
                            Option("Mean pairwise", value="mean"),
                            id="cmp-lineage-stat",
                        ),
                    ),
                    labeled(
                        "Candidates per node",
                        Input(
                            type="number",
                            id="cmp-lineage-topn",
                            min=6,
                            max=12,
                            value=8,
                            step=1,
                        ),
                    ),
                    cls="toolbar",
                ),
            ),
            Div(id="cmp-lineage"),
        ),
        # Diagnostics for choosing p (notebooks 08 & 09). Both follow the
        # "Similarity metric" selector above; the left one also follows
        # "Column distance".
        Div(
            card(
                card_head(
                    "Archetype distinctness vs p",
                    "Pairwise distance between a run's archetypes as p grows "
                    "(0 = identical, 1 = distinct). The min — the most-overlapping "
                    "pair — decreases towards a floor: past it, each added "
                    "archetype mostly duplicates an existing one. The selected "
                    "similarity metric is highlighted.",
                ),
                Div(id="cmp-distinct"),
            ),
            card(
                card_head(
                    "Sensitivity to precinct order",
                    "Similarity of each trial's archetypes to the reference run "
                    "(Hungarian-matched; one box over archetypes × trials, dashed "
                    "line = mean, whiskers to 1.5 × IQR, dots = outliers) when the "
                    "precinct order is shuffled vs when the seed is varied. "
                    "Sensitivity to both grows with p: "
                    "the decomposition turns degenerate, hopping between "
                    "alternative solutions.",
                ),
                Div(id="cmp-order"),
            ),
            cls="grid-2",
        ),
        # Controls below drive the succeeding per-p map and loadings, not the
        # sweep-wide lineage above.
        Div(
            labeled("Archetypes p", Select(id="cmp-p")),
            labeled("Archetype", Select(id="cmp-arch")),
            labeled(
                "Map shows",
                Select(
                    Option("Mean abundance", value="mean"),
                    Option("1 SD across trials", value="std"),
                    id="cmp-stat",
                ),
            ),
            labeled(
                "Top N candidates",
                Input(type="number", id="cmp-topN", min=5, max=40, value=15, step=1),
            ),
            cls="toolbar",
        ),
        # map : loadings on one row at 2fr : 3fr (the loadings grid is wide here).
        Div(
            card(Div(id="cmp-plot")),
            card(
                card_head("Loadings", None, sub_id="cmp-loadings-sub"),
                Div(id="cmp-loadings"),
            ),
            cls="grid-23",
        ),
        Div(
            card(
                card_head(
                    "Party / alliance mixing",
                    None,
                    seg_group(
                        "cmp-groupby",
                        "Group by",
                        [("party", "Party"), ("alliance", "Alliance")],
                    ),
                    sub_id="cmp-partylist-sub",
                ),
                Div(id="cmp-partylist"),
            ),
            card(
                card_head("Candidates", None, sub_id="cmp-partylist-table-sub"),
                Div(id="cmp-partylist-table"),
            ),
            cls="grid-32",
        ),
        id="tab-compare",
        cls="tab-panel",
        hidden=True,
    )


def tab_dist() -> Section:
    return Section(
        Div(
            H2("Abundance distributions", cls="section-title"),
            P(
                "Distribution of each archetype's abundance across the units at the "
                "current aggregation level.",
                cls="lede",
            ),
            cls="section-head",
        ),
        card(Div(id="dist-plots")),
        id="tab-dist",
        cls="tab-panel",
        hidden=True,
    )


def header() -> Header:
    tabs = [
        ("map", "Map / overview"),
        ("compare", "Model comparison"),
        ("dist", "Abundance distributions"),
    ]
    return Header(
        Div(
            Div(
                Div(
                    H1("PH Voting Archetypes", cls="brand"),
                    P("Spectral-unmixing explorer of PH senatorial votes", cls="subtitle"),
                    cls="brand-row",
                ),
                Nav(
                    *(A(text, href=href) for text, href in PROJECT_LINKS),
                    aria_label="Project links",
                    cls="links",
                ),
                cls="header-top",
            ),
            Div(
                Div(
                    *(
                        Button(
                            text,
                            type="button",
                            id=f"tabbtn-{key}",
                            role="tab",
                            aria_selected="true" if key == "map" else "false",
                            aria_controls=f"tab-{key}",
                            cls="tab on" if key == "map" else "tab",
                        )
                        for key, text in tabs
                    ),
                    role="tablist",
                    cls="tabs",
                ),
                Span(id="status", cls="note", aria_live="polite"),
                cls="header-tabs",
            ),
            cls="header-inner",
        ),
        cls="app-header",
    )


def asset_url(name: str) -> str:
    """``./<name>?v=<content hash>`` so a rebuilt asset is never served stale
    from the browser cache alongside a newer shell / manifest."""
    digest = hashlib.sha256((WEB / name).read_bytes()).hexdigest()[:10]
    return f"./{name}?v={digest}"


def page() -> Html:
    return Html(
        Head(
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Title("PH voting archetypes"),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(
                rel="preconnect",
                href="https://fonts.gstatic.com",
                crossorigin="anonymous",
            ),
            Link(rel="stylesheet", href=FONTS_CSS),
            Link(rel="stylesheet", href=asset_url("styles.css")),
            Script(src=PLOTLY_CDN),
        ),
        Body(
            header(),
            Div(
                sidebar(),
                Main(tab_map(), tab_compare(), tab_dist(), cls="main"),
                cls="layout",
            ),
            Script(src=asset_url("app.js")),
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
    note = (
        ""
        if (data / "manifest.json").exists()
        else "  (!) site/data is empty — run scripts/build_static.py --out site/data first"
    )
    print(f"Wrote {out}/index.html + styles.css + app.js{note}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="site", help="output dir (default: site)")
    args = ap.parse_args()
    target = Path(args.out)
    build(target if target.is_absolute() else (REPO_ROOT / target).resolve())


if __name__ == "__main__":
    main()
