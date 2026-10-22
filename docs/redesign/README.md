# Dashboard redesign: implementation brief

Target: the static site built by `scripts/build_site.py` (shell) and `web/app.js` + `web/styles.css` (behaviour and style). The data baked by `scripts/build_static.py` stays the same except for the theme palette (see below).

## Files in this folder

| file | what it is |
|---|---|
| `mockup-A.dc.html` | The agreed mockup of the **Map / overview** tab ("direction A"). |
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
#2a78d6  #eb6834  #1baf7a  #eda100  #e87ba4  #008300
```

This passes a colorblind-separation check for adjacent pairs. Three slots (aqua, yellow, magenta) are under 3:1 contrast on white, so every colored mark needs a text label next to it (chip label, chart title, legend). The dominant-archetype map uses all six at once, and no six-color set is fully colorblind-safe there, so keep the abundance map as the default view.

Sequential ramp for abundance and turnout maps (replaces `mako_r`), light to dark:

```
#e8f1fc  #cde2fb  #9ec5f4  #6da7ec  #3987e5  #256abf  #184f95  #0d366b
```

Open question for Hannah: should the abundance map use the selected archetype's own hue as its ramp instead? The mockup only shows Archetype 0, where the two are the same.

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

### Sticky header and sidebar (≥ 1024px)

```css
@media (min-width: 1024px) {
  .app-header { position: sticky; top: 0; z-index: 10; background: #fff; }
  .sidebar {
    position: sticky;
    top: var(--header-h);
    align-self: flex-start;
    max-height: calc(100vh - var(--header-h));
    overflow-y: auto;
  }
}
```

The current build already has `sticky top-0 self-start max-h-screen overflow-y-auto` on the aside. If it does not stick, check for an ancestor with `overflow` other than `visible` first. Below 1024px the sidebar stacks above the content and is not sticky.

## Out of scope for this pass

Model comparison and Abundance distributions tabs: apply the same tokens, fonts, palette and card style, but keep their layouts.
