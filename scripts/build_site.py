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
from fasthtml.svg import Path as SvgPath, Svg

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


def card_head(
    title: str, sub: str | None = None, *controls, sub_id=None, title_id=None
) -> Div:
    """Card title + caption on the left, optional controls on the right."""
    return Div(
        Div(
            H3(title, id=title_id, cls="card-title"),
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
            # Every tab shows the sweep's trial mean at this p (app.js fills it).
            field(
                "Archetypes p",
                seg_group("p", "Number of archetypes p", fill=True),
                note="Sweep trial mean; names and colors follow the lineage",
            ),
            Div(
                Label("Top N candidates", fr="topN", cls="field-label"),
                Div(
                    Button("−", type="button", id="topN-dec", cls="step", aria_label="Fewer"),
                    Input(type="number", id="topN", min=3, max=15, value=6, step=1),
                    Button("+", type="button", id="topN-inc", cls="step", aria_label="More"),
                    cls="stepper",
                ),
                id="topN-field",
                cls="field",
            ),
            cls="side-group",
        ),
        # Run summary for the selected year + method + tab (filled by app.js).
        Section(id="run-summary", cls="side-group summary"),
        cls="sidebar",
    )


def section_head(title: str, lede: str | None = None, lede_id=None) -> Div:
    return Div(
        H2(title, cls="section-title"),
        P(lede, id=lede_id, cls="lede"),
        cls="section-head",
    )


def legend_item(swatch, text: str) -> Span:
    return Span(swatch, text, cls="legend-item")


def line_swatch(stroke: str, width: float, dash: str | None = None) -> Svg:
    """A short horizontal line sample for a figure's legend row."""
    return Svg(
        SvgPath(
            d="M1 4H27",
            stroke=stroke,
            stroke_width=width,
            stroke_dasharray=dash or "none",
            stroke_linecap="round",
        ),
        width=28,
        height=8,
        aria_hidden="true",
    )


def box_swatch(fill: str, border: str = "#3a3936") -> Span:
    return Span(
        cls="box-swatch", style=f"background:{fill};border-color:{border}", aria_hidden="true"
    )


def map_figure(prefix: str) -> Figure:
    """Choropleth card: title + level/year, the map, then the color-range toggle
    and the HTML legend (filled by app.js renderMapFigure)."""
    return Figure(
        Figcaption(
            Span(id=f"{prefix}-title", cls="card-title"),
            Span(id=f"{prefix}-subtitle", cls="note"),
            cls="fig-head",
        ),
        Div(id=f"{prefix}-plot"),
        Div(
            Div(
                Span("Color range", cls="field-label"),
                seg_group(
                    f"{prefix}-range",
                    "Color range",
                    [("data", "Data range"), ("fixed", "Fixed 0 to 1")],
                ),
                id=f"{prefix}-range-row",
                cls="legend-row",
            ),
            Div(id=f"{prefix}-legend"),
            P(id=f"{prefix}-legend-note", cls="note"),
            cls="map-foot",
        ),
        cls="card",
    )


def loadings_card(prefix: str, title: str) -> Div:
    """Loadings small multiples with the Shared / Per archetype x-axis toggle."""
    return card(
        card_head(
            title,
            None,
            Div(
                Span("X-axis", cls="note"),
                seg_group(
                    f"{prefix}-axis",
                    "X-axis scaling",
                    [("shared", "Shared"), ("own", "Per archetype")],
                ),
                cls="head-control",
            ),
            sub_id=f"{prefix}-loadings-sub",
            title_id=f"{prefix}-loadings-title",
        ),
        Div(id=f"{prefix}-loadings"),
    )


def mixing_row(prefix: str) -> Div:
    """Party / alliance matrix (3fr) beside the candidates table (2fr)."""
    return Div(
        card(
            card_head(
                "Party / alliance mixing",
                None,
                seg_group(
                    f"{prefix}-groupby",
                    "Group by",
                    [("party", "Party"), ("alliance", "Alliance")],
                ),
                sub_id=f"{prefix}-partylist-sub",
            ),
            Div(id=f"{prefix}-partylist"),
        ),
        card(
            card_head("Candidates", None, sub_id=f"{prefix}-partylist-table-sub"),
            Div(id=f"{prefix}-partylist-table"),
        ),
        cls="grid-32",
    )


def tab_map() -> Section:
    return Section(
        section_head("Geographic distribution of archetypes", lede_id="map-lede"),
        Div(
            seg_group("map-quantity", "Quantity"),
            Div(id="map-arch", role="group", aria_label="Archetype", cls="chips"),
            cls="toolbar",
        ),
        # map : loadings at 3fr : 2fr (the map gets the larger share).
        Div(
            map_figure("map"),
            loadings_card("map", "Candidate weights per endmember"),
            cls="grid-32",
        ),
        mixing_row("map"),
        id="tab-map",
        cls="tab-panel",
    )


def tab_compare() -> Section:
    return Section(
        Section(
            section_head(
                "Choosing the number of archetypes",
                "How archetypes persist, split or start to duplicate as p grows, and "
                "how stable each p is to precinct order and seed.",
            ),
            # These drive the lineage and both diagnostics below.
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
                    seg_group(
                        "cmp-lineage-stat",
                        "Column distance",
                        [("min", "Min pairwise"), ("mean", "Mean pairwise")],
                    ),
                ),
                labeled(
                    "Candidates per node",
                    Input(type="number", id="cmp-lineage-topn", min=2, max=12, value=3, step=1),
                ),
                cls="toolbar",
            ),
            Figure(
                Figcaption(
                    Span("Archetype lineage", cls="card-title"),
                    Span(id="cmp-lineage-sub", cls="card-sub"),
                    cls="card-head-text wide",
                ),
                # The network is drawn at a fixed pixel width; scroll when narrow.
                Div(Div(id="cmp-lineage"), cls="scroll-x"),
                Div(
                    legend_item(
                        line_swatch("rgba(58,57,54,0.5)", 4),
                        "Matched p → p+1 (Hungarian); width and label = similarity",
                    ),
                    legend_item(
                        line_swatch("#3a3936", 1.5, "5 4"),
                        "New archetype's closest parent (split)",
                    ),
                    legend_item(
                        line_swatch("#b5b4ad", 1, "2 4"), "Other pairs with similarity ≥ 0.35"
                    ),
                    legend_item(Span("new", cls="tag-sample"), Span(id="cmp-lineage-new-label")),
                    cls="legend-rule",
                ),
                cls="card",
            ),
            # Diagnostics for choosing p (notebooks 08 & 09). Both follow the
            # "Similarity metric" selector above; the left one also follows
            # "Column distance".
            Div(
                Figure(
                    Figcaption(
                        Span("Archetype distinctness vs p", cls="card-title"),
                        Span(id="cmp-distinct-sub", cls="card-sub"),
                        cls="card-head-text",
                    ),
                    Div(id="cmp-distinct"),
                    Div(id="cmp-distinct-legend", cls="legend-plain"),
                    cls="card",
                ),
                Figure(
                    Figcaption(
                        Span("Sensitivity to precinct order", cls="card-title"),
                        Span(id="cmp-order-sub", cls="card-sub"),
                        cls="card-head-text",
                    ),
                    Div(id="cmp-order"),
                    Div(
                        legend_item(box_swatch("#6b6a65"), "Shuffled precinct order"),
                        legend_item(box_swatch("#ecebe6"), "Varying seed"),
                        Span(id="cmp-order-ylabel", cls="note"),
                        cls="legend-plain",
                    ),
                    cls="card",
                ),
                cls="grid-fit",
            ),
            cls="tab-section",
        ),
        # The archetypes at the selected p (map, loadings, mixing) are on the
        # Overview tab, which follows the sidebar p.
        id="tab-compare",
        cls="tab-panel spaced",
        hidden=True,
    )


def tab_dist() -> Section:
    return Section(
        section_head(
            "Abundance distributions",
            "Distribution of each archetype's abundance across the units at the "
            "current aggregation level, beside the candidate weights that define it.",
        ),
        Div(
            labeled(
                "Histogram x-axis",
                seg_group(
                    "dist-x", "X-axis", [("fixed", "Fixed 0 to 1"), ("own", "Per archetype")]
                ),
            ),
            labeled(
                "Y-axis",
                seg_group("dist-y", "Y-axis", [("count", "Count"), ("share", "Share of units")]),
            ),
            labeled("Bins", Input(type="number", id="dist-bins", min=5, max=60, value=20, step=1)),
            labeled(
                "Loadings x-axis",
                seg_group(
                    "dist-axis", "Loadings x-axis", [("shared", "Shared"), ("own", "Per archetype")]
                ),
            ),
            cls="toolbar",
        ),
        # One card per archetype: its abundance histogram beside its loadings.
        Div(id="dist-plots", cls="dist-rows"),
        Figure(
            Figcaption(
                Span("All archetypes on one axis", cls="card-title"),
                Span(id="dist-strip-sub", cls="card-sub"),
                cls="card-head-text",
            ),
            Div(id="dist-strip"),
            cls="card",
        ),
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
