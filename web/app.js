/* PH voting archetypes — static explorer.
 *
 * Loads the JSON/GeoJSON baked by scripts/build_static.py and draws the three
 * tabs with Plotly.js. No server: dropdowns just re-slice already-fetched data.
 */
"use strict";

const DATA = "./data";
const PLOTLY_CFG = { displayModeBar: false, responsive: true };
// Match the UI font (IBM Plex Sans, loaded via Google Fonts in build_site.py).
const FONT = { family: "'IBM Plex Sans', system-ui, sans-serif", size: 12 };
const MAP_VIEW = { style: "white-bg", center: { lon: 122.0, lat: 12.8 }, zoom: 4.6 };

// ---------------------------------------------------------------- data cache
const _cache = new Map();
async function getJSON(url) {
  if (!_cache.has(url)) {
    _cache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: ${r.status}`);
      return r.json();
    }));
  }
  return _cache.get(url);
}

// ------------------------------------------------------------------- globals
let MANIFEST = null;
const state = {
  year: null, level: "province", weighted: true, topN: 5, tab: "map",
  map: { quantity: "Archetype abundance", arch: "arch_0", groupBy: "party" },
  cmp: { p: 5, arch: "arch_0", stat: "mean", topN: 15, groupBy: "party",
    lineageTopN: 8, lineageMetric: "cos12", lineageStat: "min" },
};

// --------------------------------------------------------------------- theme
const archIndex = (c) => parseInt(c.split("_")[1], 10);
const archLabel = (c) => `Archetype ${c.split("_")[1]}`;
const FALLBACK_COLOR = "#888888";
function palette(nArch) {
  return MANIFEST.theme.categorical[String(nArch)];
}
function archColor(archCol, nArch) {
  const pal = palette(nArch);
  return pal ? pal[archIndex(archCol) % nArch] : FALLBACK_COLOR;
}
function nArchFor(year) {
  return MANIFEST.years_meta[year].n_archetypes;
}
function archCols(year) {
  return Array.from({ length: nArchFor(year) }, (_, i) => `arch_${i}`);
}
function hexToRgba(hex, alpha) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/(.)/g, "$1$1") : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
function discreteScale(colors) {
  const n = colors.length, stops = [];
  for (let i = 0; i < n; i++) {
    stops.push([i / n, colors[i]]);
    stops.push([(i + 1) / n, colors[i]]);
  }
  return stops;
}

// ------------------------------------------------------------- geo/value urls
function geoURL(year, level) {
  // province + municipality geometry is shared across years (identical
  // polygons); only region shapes are year-specific (province->region dissolve).
  if (level === "province") return `${DATA}/geo/province.geojson`;
  if (level === "municipality") return `${DATA}/geo/municipality.geojson`;
  return `${DATA}/geo/${year}_${level}.geojson`;
}
const wtag = () => (state.weighted ? "w" : "u");
const valuesURL = (year, level) => `${DATA}/values/${year}_${level}_${wtag()}.json`;
const loadingsURL = (year) => `${DATA}/loadings/${year}.json`;
const sweepURL = (year, p) => `${DATA}/sweep/${year}_p${p}.json`;
const lineageURL = (year) => `${DATA}/lineage/${year}.json`;

// -------------------------------------------------------------- chart helpers
function choropleth(divId, geo, records, colorFn, discrete) {
  // colorFn: record -> number|null (null = leave unit uncolored)
  const ids = [], z = [], text = [];
  for (const rec of records) {
    const v = colorFn(rec);
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    ids.push(rec.id); z.push(v); text.push(rec.id);
  }
  // Shared compact colorbar (no title, thin, pulled to the right edge so it
  // overlays the ocean rather than reserving a white strip the map could use).
  // The dominant-archetype case passes its own tick config in discrete.colorbar,
  // which merges on top; everything else inherits these defaults.
  const { colorbar: cbOverrides, ...traceProps } = discrete;
  const colorbar = {
    thickness: 12, len: 0.85, x: 1, xanchor: "right", y: 0.5, yanchor: "middle",
    ...(cbOverrides || {}),
  };
  const trace = {
    type: "choroplethmap", geojson: geo, featureidkey: "id",
    locations: ids, z, text, marker: { opacity: 0.9 },
    hovertemplate: "%{text}<br>%{z}<extra></extra>",
    colorbar, ...traceProps,
  };
  const layout = {
    map: MAP_VIEW, height: 640, margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)", font: FONT,
  };
  Plotly.react(divId, [trace], layout, PLOTLY_CFG);
}

function loadingsGrid(divId, payload, arch_cols, nArch, topN, title) {
  // payload: {candidates, mean:{arch:[...]}, std?:{arch:[...]}}
  const host = document.getElementById(divId);
  host.innerHTML = "";
  if (title) {
    const cap = document.createElement("p");
    cap.className = "muted"; cap.textContent = title;
    host.appendChild(cap);
  }
  const grid = document.createElement("div");
  grid.className = "plot-grid";
  host.appendChild(grid);
  for (const c of arch_cols) {
    const cell = document.createElement("div");
    cell.className = "plot-cell"; grid.appendChild(cell);
    const mean = payload.mean[c], std = payload.std ? payload.std[c] : null;
    const order = payload.candidates
      .map((name, i) => [mean[i], name, i])
      .sort((a, b) => b[0] - a[0])
      .slice(0, topN)
      .reverse();
    const trace = {
      type: "bar", orientation: "h",
      x: order.map((o) => o[0]), y: order.map((o) => o[1]),
      marker: { color: archColor(c, nArch) },
    };
    if (std) trace.error_x = { type: "data", array: order.map((o) => std[o[2]]), visible: true };
    Plotly.react(cell, [trace], {
      title: { text: archLabel(c) }, height: Math.max(300, 24 * topN),
      margin: { l: 4, r: 4, t: 34, b: 40 }, paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
      xaxis: { title: { text: "loading", standoff: 8 }, automargin: true },
      yaxis: { automargin: true },
    }, PLOTLY_CFG);
  }
}

// ------------------------------------------------------ party / alliance mixing
// Mirror of notebook 03's "Partylist mixing": sum the endmember loadings per
// group so you can see how each group's candidates spread across the voting
// archetypes. The group is either the candidate's PARTY (parsed from the label)
// or their ALLIANCE / coalition (baked per-candidate by build_static.py from
// data/elections/coalitions_2013-2025.csv). The side table's extra column shows
// the *other* dimension per candidate.
function extractParty(label) {
  // "LEGARDA, LOREN (NPC) [2]" -> "NPC"; no parenthesised party -> "X".
  const m = label.match(/\(([^)]*)\)/);
  return m ? m[1].trim() : "X";
}

// Election-result rank encoded as the trailing "[N]" in a candidate label.
const candRank = (label) => {
  const m = label.match(/\[(\d+)\]/);
  return m ? parseInt(m[1], 10) : Infinity;
};
// Drop the "(PARTY)" and "[N]" decorations for the side table.
const cleanCandidate = (label) =>
  label.replace(/\s*\([^)]*\)/, "").replace(/\s*\[\d+\]\s*$/, "").trim();

const NO_ALLIANCE = "Independent / none";

function partylistMixing(plotId, tableId, payload, arch_cols, nArch, title, mode) {
  // payload: {candidates, mean:{arch:[per-candidate loading]},
  //           alliance_list?:[[slate, ...], ...], alliance_detail?:[...]}.
  // mode: "party" (default) | "alliance". Renders the grouped-bar chart into
  // plotId and the candidates table into tableId (each in its own card).
  mode = mode === "alliance" ? "alliance" : "party";
  const hasAlliance = Array.isArray(payload.alliance_list);
  // Per-candidate placements: the group(s) the candidate belongs to, each with the
  // OTHER groups they also ran with (for the "also in …" note). In alliance mode a
  // guest / cross-endorsed candidate is placed under every slate they ran with; in
  // party mode each candidate has exactly one placement (their party).
  const placements = (i) => {
    if (mode === "alliance") {
      const lst = hasAlliance ? payload.alliance_list[i] : null;
      const slates = lst && lst.length ? lst : [NO_ALLIANCE];
      return slates.map((g) => ({
        group: g,
        others: slates.filter((x) => x !== g && x !== NO_ALLIANCE),
      }));
    }
    return [{ group: extractParty(payload.candidates[i]), others: [] }];
  };
  const extraOf = (i) => mode === "alliance"
    ? extractParty(payload.candidates[i])
    : (hasAlliance ? payload.alliance_detail[i] : "—");
  const groupHeader = mode === "alliance" ? "Alliance" : "Party";
  const extraHeader = mode === "alliance" ? "Party" : "Alliance";

  const host = document.getElementById(plotId);
  host.innerHTML = "";
  if (title) {
    const cap = document.createElement("p");
    cap.className = "muted"; cap.textContent = title;
    host.appendChild(cap);
  }
  const plot = document.createElement("div");
  plot.className = "w-full";
  host.appendChild(plot);

  const order = [];               // groups in first-seen order
  const sums = new Map();         // group -> {arch_col -> summed loading}
  const members = new Map();      // group -> [[rank, name, extra], ...]
  payload.candidates.forEach((name, i) => {
    for (const { group: g, others } of placements(i)) {
      if (!sums.has(g)) { sums.set(g, {}); members.set(g, []); order.push(g); }
      const s = sums.get(g);
      for (const c of arch_cols) s[c] = (s[c] || 0) + payload.mean[c][i];
      // Annotate the name with the candidate's other slates ("also in UNA").
      const label = others.length
        ? `${cleanCandidate(name)} (also in ${others.join(", ")})`
        : cleanCandidate(name);
      members.get(g).push([candRank(name), label, extraOf(i)]);
    }
  });
  // Largest total loading ends up at the top of the horizontal bars (Plotly puts
  // the first y-entry at the bottom), so sort ascending by total.
  const total = (p) => arch_cols.reduce((s, c) => s + (sums.get(p)[c] || 0), 0);
  const groups = order.sort((a, b) => total(a) - total(b));

  const traces = arch_cols.map((c) => ({
    type: "bar", orientation: "h", name: archLabel(c),
    y: groups, x: groups.map((p) => sums.get(p)[c] || 0),
    marker: { color: archColor(c, nArch) },
  }));
  // Light-gray separators between adjacent groups. On a categorical axis the
  // groups sit at integer indices, so the boundaries fall at the half-steps.
  const seps = [];
  for (let i = 0; i < groups.length - 1; i++) {
    seps.push({
      type: "line", xref: "paper", yref: "y", layer: "below",
      x0: 0, x1: 1, y0: i + 0.5, y1: i + 0.5,
      line: { color: "#d1d5db", width: 1 },
    });
  }
  const height = Math.max(320, groups.length * (nArch * 12 + 10) + 60);
  Plotly.react(plot, traces, {
    barmode: "group", shapes: seps, height,
    margin: { l: 4, r: 8, t: 36, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
    legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, xanchor: "left" },
    xaxis: { title: { text: "summed loading", standoff: 8 }, automargin: true },
    yaxis: { automargin: true },
  }, PLOTLY_CFG);

  // Side table (own card): candidates per group, best-ranked (by election result)
  // first, groups ordered by total loading (most prominent first). Alliance mode
  // lists the *full* slate (so it reads as the coalition's roster); party mode caps
  // at the top 5 (parties like IND are large). Each candidate gets its OWN table
  // row — name and its extra column (alliance when grouping by party, party when
  // grouping by alliance) in the same row — so they stay aligned even when either
  // one wraps; the group cell spans its candidates via rowSpan.
  const memberLimit = mode === "alliance" ? Infinity : 5;
  const candHeader = mode === "alliance" ? "Candidates (by result rank)"
                                         : "Top candidates (by result rank)";
  const tableWrap = document.getElementById(tableId);
  tableWrap.innerHTML = "";
  tableWrap.className = "overflow-y-auto";
  tableWrap.style.maxHeight = height + "px";
  const tbl = document.createElement("table");
  tbl.className = "table table-xs";
  const thead = document.createElement("thead");
  thead.innerHTML =
    `<tr><th>${groupHeader}</th><th>${candHeader}</th><th>${extraHeader}</th></tr>`;
  tbl.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const p of [...groups].reverse()) {   // largest total first
    const top = members.get(p).sort((a, b) => a[0] - b[0]).slice(0, memberLimit);
    top.forEach(([rank, name, extra], j) => {
      const tr = document.createElement("tr");
      // Stronger separator at each group's first row (daisyUI already draws a
      // faint line between every row).
      if (j === 0) tr.className = "border-t border-base-300";
      if (j === 0) {
        const tdGroup = document.createElement("td");
        tdGroup.className = "font-medium align-top";
        tdGroup.rowSpan = top.length;
        tdGroup.textContent = p;
        tr.appendChild(tdGroup);
      }
      const tdCand = document.createElement("td");
      tdCand.className = "align-top";
      tdCand.textContent = rank === Infinity ? name : `${rank}. ${name}`;
      const tdExtra = document.createElement("td");
      tdExtra.className = "align-top text-xs opacity-70";
      tdExtra.textContent = extra || "—";
      tr.appendChild(tdCand); tr.appendChild(tdExtra);
      tbody.appendChild(tr);
    });
  }
  tbl.appendChild(tbody);
  tableWrap.appendChild(tbl);
}

// --------------------------------------------------------------------- tab: map
async function renderMap() {
  const year = state.year, level = state.level, nArch = nArchFor(year);
  const [geo, vals, loadings] = await Promise.all([
    getJSON(geoURL(year, level)),
    getJSON(valuesURL(year, level)),
    getJSON(loadingsURL(year)),
  ]);
  const cols = archCols(year);

  // keep the archetype selector valid for this year
  if (!cols.includes(state.map.arch)) state.map.arch = "arch_0";
  fillArchSelect("map-arch", cols, state.map.arch, nArch);

  const kind = state.map.quantity, sel = state.map.arch;
  let colorFn, discrete;
  if (kind === "Dominant archetype") {
    const colors = palette(nArch);
    colorFn = (r) => (r.dominant == null ? null : parseInt(r.dominant, 10) + 0.5);
    discrete = {
      colorscale: discreteScale(colors), zmin: 0, zmax: nArch,
      colorbar: {
        tickmode: "array",
        tickvals: cols.map((_, i) => i + 0.5), ticktext: cols.map(archLabel),
      },
    };
  } else if (kind === "Turnout") {
    colorFn = (r) => (r.turnout == null ? null : r.turnout);
    discrete = { colorscale: MANIFEST.theme.sequential };
  } else {
    colorFn = (r) => (r[sel] == null ? null : r[sel]);
    discrete = { colorscale: MANIFEST.theme.sequential };
  }
  choropleth("map-plot", geo, vals.records, colorFn, discrete);

  const cap = loadings.std
    ? "Error bars: std across the sweep's trials at this archetype count."
    : "Run the sweep for this year to add trial-based error bars.";
  loadingsGrid("map-loadings", loadings, cols, nArch, state.topN,
    "Candidate weights per endmember (MVSA, national-level). " + cap);

  const mgb = state.map.groupBy;
  partylistMixing("map-partylist", "map-partylist-table", loadings, cols, nArch,
    `Summed endmember loading per ${mgb}, grouped by archetype.`, mgb);
}

// Lineage network: how archetypes persist or split as p grows across the
// sweep. Columns are pinned at x = p; each node is a box listing its top-N
// candidates (surname, strongest first) with a border in the archetype color;
// edge width + label = the selected similarity metric between the two loading
// columns. The Hungarian-matched lineage (full cosine, split children
// included) is solid; unmatched pairs above a floor are kept as faint
// context. Above each column: that p's min/mean pairwise distance
// (0 = identical … 1 = distinct). Independent of p/level/weighting.
const LINEAGE_SIM_FLOOR = 0.35; // hide near-orthogonal unmatched pairs
const LINEAGE_NODE_FONT = 9; // px, node box text (box widths are measured off it)
const LINEAGE_METRICS = {
  cos12: "cosine (top 12)", spearman: "Spearman r",
  rbo: "RBO", jac12: "Jaccard (top 12)",
};

// Pixel width of a node box's widest text line (the annotation auto-sizes to
// its text), measured with a canvas so edges can attach to the box border.
const _measureCtx = document.createElement("canvas").getContext("2d");
function lineageBoxHalfWidthPx(rows) {
  let w = 0;
  rows.forEach((ln, r) => {
    _measureCtx.font =
      `${r === 0 ? "bold " : ""}${LINEAGE_NODE_FONT}px ${FONT.family}`;
    w = Math.max(w, _measureCtx.measureText(ln).width);
  });
  // half the text + annotation borderpad (2) + border (1.5) + a hair of slack
  return w / 2 + 2 + 1.5 + 1;
}

async function renderLineage(divId) {
  const host = document.getElementById(divId);
  const lin = await getJSON(lineageURL(state.year)).catch(() => null);
  if (!lin) { host.textContent = ""; return; }
  const topN = state.cmp.lineageTopN;
  const metric = state.cmp.lineageMetric, stat = state.cmp.lineageStat;
  const simOf = (l) => l.sims[metric];
  const ps = lin.ps, maxP = ps[ps.length - 1];

  const links = lin.links.filter((l) =>
    l.matched || l.split || simOf(l) >= LINEAGE_SIM_FLOOR);

  // Vertical layout: first column in k order, then each column ordered by the
  // similarity-weighted mean y of its predecessors (barycenter) to limit
  // edge crossings. y runs 0 (top) → 1 (bottom).
  const byP = new Map(ps.map((p) => [p, []]));
  lin.nodes.forEach((n, i) => byP.get(n.p).push(i));
  const y = new Array(lin.nodes.length).fill(0.5);
  byP.get(ps[0]).forEach((i, r, col) => { y[i] = (r + 0.5) / col.length; });
  for (let c = 1; c < ps.length; c++) {
    const col = byP.get(ps[c]);
    const pulls = new Map(col.map((i) => [i, []]));
    for (const l of links) {
      if (lin.nodes[l.source].p === ps[c - 1] && pulls.has(l.target)) {
        pulls.get(l.target).push([y[l.source], Math.max(simOf(l), 0)]);
      }
    }
    col
      .map((i, r) => {
        const w = pulls.get(i).reduce((a, [, s]) => a + s, 0);
        const b = w > 0
          ? pulls.get(i).reduce((a, [yy, s]) => a + yy * s, 0) / w
          : (r + 0.5) / col.length;
        return [i, b];
      })
      .sort((a, b) => a[1] - b[1])
      .forEach(([i], r) => { y[i] = (r + 0.5) / col.length; });
  }

  // Node box text (needed before the edges: box widths set where edges end).
  const nodeRows = lin.nodes.map((n) => {
    const names = n.top.slice(0, topN).map((t) => t.name);
    const rows = [names[0]];
    for (let r = 1; r < names.length; r += 2) {
      rows.push(names.slice(r, r + 2).join(" · "));
    }
    return rows;
  });

  // Box half-widths in x-units, so each edge attaches to the border of its
  // boxes, vertically centered: right-side middle of the source box to
  // left-side middle of the target box.
  const plotPx = Math.max(300, (host.clientWidth || 1100) - 20); // minus l/r margins
  const unitsPerPx = (maxP - ps[0] + 0.9) / plotPx;
  const halfW = nodeRows.map((rows) => lineageBoxHalfWidthPx(rows) * unitsPerPx);
  const edgeEnds = (l) => {
    const s = lin.nodes[l.source], t = lin.nodes[l.target];
    return {
      x0: s.p + halfW[l.source], y0: y[l.source],
      x1: t.p - halfW[l.target], y1: y[l.target],
    };
  };

  // Edges as below-layer line shapes (per-edge width).
  const shapes = links.map((l) => {
    const e = edgeEnds(l);
    return {
      type: "line", layer: "below", ...e,
      line: {
        width: 0.5 + 6 * Math.max(simOf(l), 0),
        color: l.matched || l.split
          ? "rgba(100,120,160,0.55)" : "rgba(100,120,160,0.16)",
      },
    };
  });

  // Per-edge value labels, staggered along the edge so labels of crossing
  // edges rarely land on top of each other; they double as the hover target
  // (hover lists every metric, not just the selected one).
  const edgeT = (l) => 0.3 + 0.13 * ((l.source + l.target) % 4);
  const edgeLabels = {
    type: "scatter", mode: "text", hoverinfo: "text", showlegend: false,
    x: links.map((l) => {
      const e = edgeEnds(l);
      return e.x0 + (e.x1 - e.x0) * edgeT(l);
    }),
    y: links.map((l) => {
      const e = edgeEnds(l);
      return e.y0 + (e.y1 - e.y0) * edgeT(l);
    }),
    text: links.map((l) => simOf(l).toFixed(2)),
    textposition: "top center",
    textfont: {
      family: FONT.family, size: 8.5,
      color: links.map((l) => l.matched || l.split
        ? "rgba(70,85,120,0.9)" : "rgba(100,120,160,0.55)"),
    },
    hovertext: links.map((l) => {
      const s = lin.nodes[l.source], t = lin.nodes[l.target];
      const kind = l.split ? " · split" : l.matched ? " · matched" : "";
      return `p${s.p}·A${s.k} ${s.label} → p${t.p}·A${t.k} ${t.label}${kind}` +
        `<br>cosine (top 12) ${l.sims.cos12} · Spearman r ${l.sims.spearman}` +
        `<br>RBO ${l.sims.rbo} · Jaccard (top 12) ${l.sims.jac12}`;
    }),
  };

  // Nodes: one annotation per archetype — top candidate bold on its own line,
  // the rest of the top-N packed two per line to keep the plot compact, box
  // border in the archetype color. Hover lists full labels + loadings.
  const annotations = lin.nodes.map((n, i) => {
    const rows = nodeRows[i].map((r, j) => (j === 0 ? `<b>${r}</b>` : r));
    return {
      x: n.p, y: y[i], xanchor: "center", yanchor: "middle",
      align: "center", showarrow: false,
      font: { family: FONT.family, size: LINEAGE_NODE_FONT },
      bordercolor: archColor(`arch_${n.k}`, n.p), borderwidth: 1.5, borderpad: 2,
      bgcolor: "rgba(255,255,255,0.85)",
      text: rows.join("<br>"),
      hovertext: `<b>p = ${n.p} · archetype ${n.k}</b><br>` +
        n.top.slice(0, topN).map((t) => `${t.full} — ${t.w}`).join("<br>"),
    };
  });

  // Within-p distinctness readout above each column: the min or mean pairwise
  // distance (0 = identical … 1 = distinct) between that p's archetypes,
  // under the selected metric (notebook 08's p-sweep scalars).
  for (const p of ps) {
    const d = lin.distinct && lin.distinct[p] && lin.distinct[p][metric];
    if (!d) continue;
    annotations.push({
      x: p, xref: "x", y: 1, yref: "paper", yanchor: "bottom", showarrow: false,
      font: { family: FONT.family, size: 9.5, color: "rgba(90,100,125,0.95)" },
      text: `${stat} d = ${d[stat].toFixed(2)}`,
      hovertext: `${stat} pairwise distance between the ${p} archetypes<br>` +
        `(${LINEAGE_METRICS[metric]}; 0 = identical, 1 = distinct)`,
    });
  }

  const nodeLines = 1 + Math.ceil((topN - 1) / 2);
  Plotly.react(divId, [edgeLabels], {
    height: Math.max(420, maxP * (nodeLines * 11 + 26)),
    margin: { l: 10, r: 10, t: 24, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
    shapes, annotations,
    xaxis: {
      title: { text: "number of archetypes p" },
      tickvals: ps, range: [ps[0] - 0.45, maxP + 0.45],
      showgrid: false, zeroline: false, fixedrange: true,
    },
    yaxis: {
      visible: false, range: [1.02, -0.02], fixedrange: true,
    },
  }, PLOTLY_CFG);
}

// Edge attachment points are computed from the plot's pixel width, so re-derive
// them when the window resizes (Plotly's own responsive reflow keeps the boxes
// at their pixel size while the axis units stretch underneath them).
let _lineageResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(_lineageResizeTimer);
  _lineageResizeTimer = setTimeout(() => {
    if (state.tab === "compare") renderLineage("cmp-lineage");
  }, 250);
});

// ----------------------------------------------------------------- tab: compare
async function renderCompare() {
  const year = state.year, level = state.level, nArch = nArchFor(year);
  const p = state.cmp.p;
  await renderLineage("cmp-lineage");
  const [geo, sweep] = await Promise.all([
    getJSON(geoURL(year, level)),
    getJSON(sweepURL(year, p)),
  ]);
  const cols = sweep.arch_cols;
  if (!cols.includes(state.cmp.arch)) state.cmp.arch = "arch_0";
  fillArchSelect("cmp-arch", cols, state.cmp.arch, p);

  const showStd = state.cmp.stat === "std";
  const recs = sweep.levels[level][wtag()][showStd ? "std" : "mean"];
  const sel = state.cmp.arch;
  choropleth("cmp-plot", geo, recs, (r) => (r[sel] == null ? null : r[sel]),
    { colorscale: MANIFEST.theme.sequential });

  loadingsGrid("cmp-loadings",
    { candidates: sweep.candidates, mean: sweep.loadings_mean, std: sweep.loadings_std },
    cols, p, state.cmp.topN, "Loadings (mean ± std over trials) at p = " + p);

  const cgb = state.cmp.groupBy;
  partylistMixing("cmp-partylist", "cmp-partylist-table",
    { candidates: sweep.candidates, mean: sweep.loadings_mean,
      alliance_list: sweep.alliance_list, alliance_detail: sweep.alliance_detail },
    cols, p, `Summed endmember loading per ${cgb} at p = ${p}, grouped by archetype.`, cgb);
}

// ------------------------------------------------------------- tab: distributions
async function renderDist() {
  const year = state.year, level = state.level, nArch = nArchFor(year);
  const vals = await getJSON(valuesURL(year, level));
  const cols = archCols(year);
  const host = document.getElementById("dist-plots");
  host.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "plot-grid"; host.appendChild(grid);
  const unit = MANIFEST.level_labels[level].toLowerCase();
  for (const c of cols) {
    const cell = document.createElement("div");
    cell.className = "plot-cell"; grid.appendChild(cell);
    const x = vals.records.map((r) => r[c]).filter((v) => v != null);
    Plotly.react(cell, [{
      type: "histogram", x, nbinsx: 40, marker: { color: archColor(c, nArch) },
    }], {
      title: { text: archLabel(c) }, height: 280,
      margin: { l: 40, r: 8, t: 34, b: 30 }, paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)", font: FONT, xaxis: { title: { text: "abundance" } },
      yaxis: { title: { text: `# ${unit}s` } },
    }, PLOTLY_CFG);
  }
}

// ------------------------------------------------------------------- rendering
async function renderActive() {
  document.getElementById("status").textContent = "Loading…";
  try {
    if (state.tab === "map") await renderMap();
    else if (state.tab === "compare") await renderCompare();
    else await renderDist();
    document.getElementById("status").textContent = "";
  } catch (e) {
    document.getElementById("status").textContent = "Error: " + e.message;
    console.error(e);
  }
}

function updateCaption() {
  const m = MANIFEST.years_meta[state.year];
  document.getElementById("sidebar-caption").textContent =
    `${state.year} senatorial race · ${m.n_archetypes} endmembers · ` +
    `${m.candidate_labels.length} candidates`;
}

// --------------------------------------------------------------------- controls
function fillSelect(id, options, value, labelFn) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  for (const o of options) {
    const opt = document.createElement("option");
    opt.value = o; opt.textContent = labelFn ? labelFn(o) : o;
    if (String(o) === String(value)) opt.selected = true;
    el.appendChild(opt);
  }
}
function fillArchSelect(id, cols, value, nArch) {
  fillSelect(id, cols, value, archLabel);
}

function switchTab(tab) {
  state.tab = tab;
  for (const t of ["map", "compare", "dist"]) {
    document.getElementById(`tab-${t}`).hidden = t !== tab;
    document.getElementById(`tabbtn-${t}`).classList.toggle("tab-active", t === tab);
  }
  // compare uses the internal name "compare"; button/section id is "compare"
  renderActive();
}

// ------------------------------------------------------------------------- init
async function init() {
  MANIFEST = await getJSON(`${DATA}/manifest.json`);
  state.year = MANIFEST.default_year;

  fillSelect("year", MANIFEST.years, state.year);
  fillSelect("cmp-p", MANIFEST.years_meta[state.year].sweep_ps, state.cmp.p);

  // level radio
  const levels = document.getElementById("levels");
  levels.innerHTML = "";
  for (const lvl of MANIFEST.levels) {
    const lab = document.createElement("label");
    lab.className = "flex items-center gap-2 cursor-pointer text-sm";
    const r = document.createElement("input");
    r.type = "radio"; r.name = "level"; r.value = lvl;
    r.className = "radio radio-xs";
    r.checked = lvl === state.level;
    r.addEventListener("change", () => { state.level = lvl; renderActive(); });
    lab.appendChild(r);
    lab.appendChild(document.createTextNode(MANIFEST.level_labels[lvl]));
    levels.appendChild(lab);
  }

  fillSelect("map-quantity", MANIFEST.value_kinds, state.map.quantity);

  // wire controls
  document.getElementById("year").addEventListener("change", (e) => {
    state.year = e.target.value;
    fillSelect("cmp-p", MANIFEST.years_meta[state.year].sweep_ps, state.cmp.p);
    updateCaption(); renderActive();
  });
  document.getElementById("topN").addEventListener("change", (e) => {
    state.topN = +e.target.value; if (state.tab === "map") renderActive();
  });
  document.getElementById("weighted").addEventListener("change", (e) => {
    state.weighted = e.target.checked; renderActive();
  });
  document.getElementById("map-quantity").addEventListener("change", (e) => {
    state.map.quantity = e.target.value; renderActive();
  });
  document.getElementById("map-arch").addEventListener("change", (e) => {
    state.map.arch = e.target.value; renderActive();
  });
  document.getElementById("map-groupby").addEventListener("change", (e) => {
    state.map.groupBy = e.target.value; if (state.tab === "map") renderActive();
  });
  document.getElementById("cmp-p").addEventListener("change", (e) => {
    state.cmp.p = +e.target.value; renderActive();
  });
  document.getElementById("cmp-arch").addEventListener("change", (e) => {
    state.cmp.arch = e.target.value; renderActive();
  });
  document.getElementById("cmp-stat").addEventListener("change", (e) => {
    state.cmp.stat = e.target.value; renderActive();
  });
  document.getElementById("cmp-groupby").addEventListener("change", (e) => {
    state.cmp.groupBy = e.target.value; if (state.tab === "compare") renderActive();
  });
  document.getElementById("cmp-topN").addEventListener("change", (e) => {
    state.cmp.topN = +e.target.value; renderActive();
  });
  document.getElementById("cmp-lineage-topn").addEventListener("change", (e) => {
    state.cmp.lineageTopN = Math.min(12, Math.max(6, +e.target.value || 8));
    e.target.value = state.cmp.lineageTopN;
    if (state.tab === "compare") renderLineage("cmp-lineage");
  });
  document.getElementById("cmp-lineage-metric").addEventListener("change", (e) => {
    state.cmp.lineageMetric = e.target.value;
    if (state.tab === "compare") renderLineage("cmp-lineage");
  });
  document.getElementById("cmp-lineage-stat").addEventListener("change", (e) => {
    state.cmp.lineageStat = e.target.value;
    if (state.tab === "compare") renderLineage("cmp-lineage");
  });
  for (const [t, id] of [["map", "tabbtn-map"], ["compare", "tabbtn-compare"], ["dist", "tabbtn-dist"]]) {
    document.getElementById(id).addEventListener("click", () => switchTab(t));
  }

  updateCaption();
  renderActive();
}

init();
