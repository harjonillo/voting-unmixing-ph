# Dashboard redesign: implementation brief

Target: the static site built by `scripts/build_site.py` (shell) and `web/app.js` + `web/styles.css` (behaviour and style). The data baked by `scripts/build_static.py` stays the same except for the theme palette (see below).

## Files in this folder

| file | what it is |
|---|---|
| `mockup-A.dc.html` | The agreed mockup of the **Map / overview** tab ("direction A"). |
| `mockup-A-compare.dc.html` | **Model comparison** tab in the same style. |
| `mockup-A-distributions.dc.html` | **Abundance distributions** tab in the same style. |
| `type-scale.dc.html` | The type scale sheet (ratio 1.2). Only the Instrument Sans column applies. |

Both files are design-canvas source, not production code. They use a small template format: markup inside `<x-dc>`, loops as `<sc-for list="{{...}}">`, conditionals as `<sc-if>`, and `{{holes}}` filled from `renderVals()` in the `<script type="text/x-dc">` block at the bottom. Read them as a spec. Rebuild the layout with FastHTML in `build_site.py` and the charts with Plotly in `app.js`. Don't copy the template syntax.

The numbers in `renderVals()` of `mockup-A.dc.html` are real 2025 MVSA values: endmember loadings from `data/processed/2025/endmembers.csv`, error bars from the p = 6 sweep SDs, alliance sums from `data/elections/coalitions_2013-2025.csv`, and result ranks. They are useful for checking the build. The map shading in the mockup is **placeholder**, not real abundances.

## Stack

- Keep FastHTML as the shell generator in `build_site.py`.
- Drop Tailwind (Play CDN) and daisyUI. Move all styling into `web/styles.css` with CSS variables. The controls in the mockup are plain buttons, inputs and tables, so no component library is needed.
- Plotly stays.

## Tokens

Type scale, base 16px, ratio 1.2:

```css
:root {
  --fs--2: 0.694rem;  /* 11.1px  captions, axis ticks, overline labels */
  --fs--1: 0.833rem;  /* 13.3px  labels, controls, table cells */
  --fs-0:  1rem;      /* 16px    body */
  --fs-1:  1.2rem;    /* 19.2px  card titles */
  --fs-2:  1.44rem;   /* 23.0px  page title, section headings */
  --fs-3:  1.728rem;  /* 27.6px  (reserve) */
}
```

Fonts (Google Fonts): **Instrument Sans** 400/500/600 for all UI text, **IBM Plex Mono** 400/500 for numbers (stats, ticks, table values). Update `FONT` in `app.js` to Instrument Sans so Plotly matches the page.

Colors:

| role | value |
|---|---|
| page and card background | `#ffffff` |
| primary ink | `#0b0b0b` |
| secondary ink | `#52514e` |
| muted ink (must stay ≥ 4.5:1 on white) | `#6b6a65` |
| card border | `#e3e2dc` |
| hairline / row divider | `#ecebe6`, `#f1f0ec` |
| axis / zero line | `#c3c2b7` |
| segmented-control track | `#f7f6f3` |
| selected control | `#0b0b0b` background, white text |

UI chrome is black and gray only. Color is reserved for data.

## Archetype palette

Replace the husl `theme.categorical` in `build_static.py` with this fixed order (slot i = Archetype i, never cycled):

```
#3c73e1  #fe654f  #169873  #ffae03  #6b4b3e  #9ebd6e
Crayola Blue, Tomato, Shamrock, Orange, Mauve Bark, Muted Olive
```

The 7th slot, Vintage Berry `#993955`, is for lineage nodes with no counterpart (see the Model comparison tab).

The order puts blue, tomato, a green and orange first, because most views show p ≤ 4. Shamrock is the green there: under simulated deuteranopia it stays about three times further from blue, tomato and orange than Muted Olive does (ΔE ≈ 43 vs 14). Olive is close to tomato for red-green colorblind viewers, so it takes the last slot, where the two only meet at p ≥ 6. Three slots (tomato, orange, olive) are under 3:1 contrast on white, so every colored mark needs a text label next to it (chip label, chart title, legend), and none of them should be used for text. The dominant-archetype map uses all six at once, and no six-color set is fully colorblind-safe there, so keep the abundance map as the default view.

Map ramps (replace `mako_r`), light to dark:

- Abundance (and its 1 SD map): the selected archetype's own hue, from a pale tint through the color to a darker shade.
- Turnout: warm grays, so turnout never reads as an archetype.

```
#f4f3ef  #dddcd5  #c3c2b9  #a5a49c  #86857e  #686761  #4a4945  #2b2a28
```

## Layout (Map / overview tab)

- **Header**: title, subtitle, and project links on one row. Underline tabs below.
- **Sidebar** (≈280px), three groups:
  - Data: election year as a segmented control, aggregation level as radios, the weighting checkbox.
  - Model: MVSA/NMF segmented control with the note "Abundances are SUNSAL for both", and Top N as a number input with −/+ buttons.
  - Run summary in mono: p, HySime k, candidate count, RMSE (from `meta.json`).
- **Main column**:
  1. Section heading and one-line description. Then a Quantity segmented control (Abundance / Dominant archetype / Turnout) and archetype chips (color dot + "A0"…"A5") that replace the archetype dropdown.
  2. A grid with two columns, **3fr map : 2fr loadings** (the map gets the larger share).
  3. A second grid, **3fr alliance matrix : 2fr candidates table**.

Cards: 1px `#e3e2dc` border, 10px radius, 20px padding, no shadow.

## Interactions to implement

### Map color range toggle ("Data range" / "Fixed 0 to 1")

- Data range: Plotly autoscale (`zauto: true`), as now.
- Fixed: `zmin: 0, zmax: 1`.
- Applies to the abundance and turnout maps, not to the dominant-archetype map. Put it in the map card under the map, beside the colorbar. Persist it in `state.map`.

### Loadings x-axis toggle ("Shared" / "Per archetype")

- Shared: compute one range over all archetypes shown, including error bars: `[min(0, min(mean − sd)), max(mean + sd)]`, rounded out to a tick step. Apply it as `xaxis.range` on every small multiple.
- Per archetype: each chart gets the same calculation over its own rows.
- Persist it in `state`.

### Loadings small multiples (keep the original Plotly detail)

- Horizontal bars, one chart per archetype, stacked in **one column** (the column is narrow).
- y labels: `Name, First` plus party and result rank, e.g. `Dela Rosa, Bato PDPLBN [3]`.
- Error bars with caps, a zero line, light gridlines, and an x-axis title "loading".
- Keep the NNDSVD dotted-line overlay and its caption for NMF.
- Row height about 22px, so a chart is roughly `22 × topN + 60` px tall.

### Party / alliance mixing

- Replace the grouped bar chart in `partylistMixing()` with an **alliance × archetype matrix**: rows are groups, columns are archetypes (header shows the color dot + "A0"…), and each cell holds the summed loading.
- Shading is diverging, symmetric around 0: red `#a3302f` → gray `#f0efec` → blue `#184f95`. Scale by the max |value| in the table; the mockup uses sqrt easing so small values still show. Switch text to white on dark cells.
- Show the value in each cell (mono) and a small gradient key below.
- Keep the Party / Alliance toggle. Order rows by total loading, as now.
- These are summed loadings, not correlations; label them so.

### Candidates table

- Keep the current behaviour: alliance mode lists the full slate, party mode the top 5.
- Rows sorted by result rank and shown as `12. Marcos, Imee`, with "also in …" notes for guests. The group cell spans its rows (rowspan).
- Scroll box with a sticky table header.

### App shell and scrolling (replaces sticky positioning)

The page is a fixed-height app shell: the header and sidebar stay put, and only the content pane scrolls. Its scrollbar sits on the pane's **left** edge, right next to the sidebar. Apply the same layout to all three tabs.

```css
.shell { height: 100vh; display: flex; flex-direction: column; }
.shell-body { flex: 1 1 auto; min-height: 0; display: flex; align-items: stretch;
              width: 100%; max-width: 1440px; margin: 0 auto; }
.side { flex: 0 0 272px; overflow-y: auto; }   /* scrolls on its own only if taller than the window */
.pane { flex: 1 1 auto; min-width: 0; overflow-y: auto; direction: rtl; }  /* rtl puts the scrollbar on the left */
.pane > * { direction: ltr; }

@media (max-width: 900px) {            /* phones: one normal scrolling page */
  .shell { height: auto; }
  .shell-body { flex-wrap: wrap; }
  .side { flex: 1 1 100%; overflow: visible; }
  .pane { overflow: visible; direction: ltr; border-left: 0; }
}
```

Scrollbars: minimal and always visible, matching the tab underline. A 1px hairline track (`#e3e2dc`) with a 2px black (`#0b0b0b`) thumb that thickens to 4px on hover. Use it on `.pane`, `.side` and every scrollable card (candidates table, matrix, lineage figure).

```css
.scroll::-webkit-scrollbar { width: 8px; height: 8px; background: transparent; }
.scroll::-webkit-scrollbar-track:vertical {
  background: linear-gradient(90deg, transparent 3.5px, #e3e2dc 3.5px, #e3e2dc 4.5px, transparent 4.5px); }
.scroll::-webkit-scrollbar-track:horizontal {
  background: linear-gradient(180deg, transparent 3.5px, #e3e2dc 3.5px, #e3e2dc 4.5px, transparent 4.5px); }
.scroll::-webkit-scrollbar-thumb { background: #0b0b0b; background-clip: padding-box;
  border: 3px solid transparent; border-radius: 0; }
.scroll::-webkit-scrollbar-thumb:hover,
.scroll::-webkit-scrollbar-thumb:active { border-width: 2px; }
.scroll::-webkit-scrollbar-corner { background: transparent; }
@supports not selector(::-webkit-scrollbar) {   /* Firefox: closest match */
  .scroll { scrollbar-width: thin; scrollbar-color: #0b0b0b transparent; }
}
```

Do not also set `scrollbar-color`/`scrollbar-width` for Chrome: once those standard properties are set, Chrome ignores the `::-webkit-scrollbar` rules.

Plotly charts inside the pane resize with the pane, not the window. Keep `responsive: true` and call `Plotly.Plots.resize` on the visible charts when the pane's width changes (a `ResizeObserver` on `.pane`).

### Small touches

- **Logo mark** left of the title: six dots in the archetype palette at the corners of a hexagon, every pair joined by a 0.75px `#d6d5cf` line (a 2-D view of the simplex). It rotates 60° on hover of the title link (0.6s ease-out). The SVG is in `mockup-A.dc.html`.
- **Wordmark:** the title only, in Bricolage Grotesque 700. Everything else stays Instrument Sans.
- **Archetype chips:** the selected chip's background is its archetype color at about 14% alpha (`#3c73e1` + `24`). The dot scales up 1.4× on hover.
- **Loadings bars** animate `left`/`width` over 0.45s when the x-axis toggle changes. In Plotly, use `Plotly.animate` or a `transition` in the layout.
- **Footer line** at the end of the pane, with a dots-only version of the mark: "Unmixed with HySime, MVSA and SUNSAL at the National Institute of Physics, UP Diliman."
- Respect `prefers-reduced-motion: reduce`: no rotation, no bar animation.

## Model comparison tab (`mockup-A-compare.dc.html`)

Same header, sidebar and card style as Overview. The sidebar drops Top N and shows sweep facts instead: p range, trials per p, HySime k.

Data in the mockup: the distinctness values and order-sensitivity box stats are real (`data/distinctness/2025.json`, `data/order_sensitivity/2025.json`), and so are the p = 5 loadings with SDs. I recomputed the lineage from the sweep's mean loadings (full-cosine Hungarian match p → p+1, plus the extra child linked to its closest parent), so it may differ slightly from the baked `lineage/2025.json`.

### Controls (top of tab)

Similarity metric (select), Column distance (Min / Mean segmented), Candidates per node (number). These drive the lineage and both diagnostics, as now.

### Archetype lineage

- One column per p. Above each column: `p = N` and `min d 0.xx` (mono). The column for the HySime k is in primary ink, the rest muted.
- Nodes are fixed-width boxes (132px) with a 1.5px border in the archetype color, white fill, 6px radius. Line 1: top candidate in semibold plus a mono tag (`A1`, or `new`). Line 2: the next candidates joined with ` · `, muted.
- Links are cubic Béziers from the right middle of the source box to the left middle of the target box:
  - matched: solid, `rgba(58,57,54,0.42)`, width `1 + 5 × sim`
  - split (new archetype's closest parent): 1.5px dashed `5 4`, `#3a3936`
  - other pairs ≥ 0.35: 1px dotted `2 4`, `#b5b4ad`, no label
- Similarity labels on matched and split links only: mono, small, white background.
- **Color by lineage, anchored to the Overview run.** Match the sweep's archetypes at p = k (HySime k) to the main run's archetypes, give them the main run's colors, then propagate along matched links backwards to p = 2 and forwards to p_max. A node with no counterpart at p = k takes the next free slot (7th slot `#993955`). Past 8 slots, fold extra nodes into a neutral gray. This needs a small addition to the bake: a `color_slot` per lineage node.
- A legend row under the figure explains the three link styles and the "no counterpart" color.
- The figure is wider than a narrow screen: wrap it in an `overflow-x: auto` box.

### Archetype distinctness vs p

- The selected metric is a 2.5px line in primary ink with 8px point markers and a direct label at its right end. The other five metrics are 1.25px lines in `#c3c2b7`, unlabelled, and named in a legend row below.
- A dashed vertical marker at p = HySime k, labelled `HySime k = 6`.
- y fixed 0 to 1 with light gridlines, x = p.

### Sensitivity to precinct order

- Grouped box plot per p. The two arms are told apart by fill lightness, not hue, so they never read as archetypes: shuffled order `#6b6a65` fill with a white median; varying seed `#ecebe6` fill with a dark median. Both get a `#3a3936` outline.
- Whiskers to 1.5 × IQR, outlier dots, and the mean as a small white diamond with a dark outline.
- y range −0.1 to 1.0 (outliers go slightly below 0).

### Archetypes at a chosen p

- p as a segmented control (2 … 7), Map shows (Mean abundance / 1 SD across trials), archetype chips colored by lineage.
- Then the same map : loadings grid (3fr : 2fr) as Overview, with both toggles. Then the same party/alliance matrix and candidate table as Overview (a placeholder in the mockup).

## Abundance distributions tab (`mockup-A-distributions.dc.html`)

The histogram shapes in the mockup are **placeholder**. Bin the real per-unit values from `values/{year}_{level}_{w}.json`.

- Controls: X-axis (Fixed 0 to 1 / Per archetype), Y-axis (Count / Share of units), Bins (number, default 20; 40 bins over ~80 provinces leaves most bins empty).
- Small multiples, one card per archetype in a `repeat(auto-fill, minmax(300px, 1fr))` grid. Bars in the archetype color with 2px gaps, plus light horizontal gridlines.
- **Shared y-scale across all cards**, so heights compare directly.
- A dashed median line labelled `median`. Hover on a bar: bin range and count.
- A new card, **All archetypes on one axis**: one row per archetype on a shared 0 to 1 axis, with a jittered dot per unit (archetype color, 0.75 opacity), an outlined quartile box and a median tick. Hover on a dot: unit name and value.
- The sidebar run summary shows the unit count at the current level.
