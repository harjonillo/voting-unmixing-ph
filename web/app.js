/* PH voting archetypes — static explorer.
 *
 * Loads the JSON/GeoJSON baked by scripts/build_static.py and draws the three
 * tabs with Plotly.js. No server: dropdowns just re-slice already-fetched data.
 * Mirrors the Streamlit app (app/tabs/*, app/components/*).
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
  map: { quantity: "Archetype abundance", arch: "arch_0" },
  cmp: { p: 5, arch: "arch_0", stat: "mean", topN: 15, linTopN: 8, linFlows: true },
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
}

// d3.cluster tree of how archetypes split as the endmember count p grows, drawn
// left→right (depth = p). Each node lists its top-N senators (by loading, home =
// argmax archetype), coloured by archetype; a senator new to a node vs its parent
// is bold with a "+", so the exchange reads down each branch. Split-off nodes get
// a "△ <candidate>" header. Rendered with D3/SVG, not Plotly. Independent of
// p/level/weighting.
async function renderLineage(divId) {
  const host = document.getElementById(divId);
  const lin = await getJSON(lineageURL(state.year)).catch(() => null);
  if (!lin) { host.textContent = ""; return; }
  const hi = MANIFEST.theme.highlight;
  const nodes = lin.nodes;
  const N = Math.max(5, Math.min(10, state.cmp.linTopN || 8));

  // Lineage tree from the links: parent/children, plus split targets + their
  // emerging candidate. Roots (p = min_p) have no parent.
  const childrenOf = new Map(), parentOf = new Map();
  const isSplit = new Set(), emergingOf = new Map();
  for (const l of lin.links) {
    if (!childrenOf.has(l.source)) childrenOf.set(l.source, []);
    childrenOf.get(l.source).push(l.target);
    parentOf.set(l.target, l.source);
    if (l.split) { isSplit.add(l.target); emergingOf.set(l.target, l.emerging); }
  }
  const rootIdxs = nodes.map((_, i) => i).filter((i) => !parentOf.has(i));
  const toTree = (i) => ({ idx: i, children: (childrenOf.get(i) || []).map(toTree) });
  // Synthetic root ties the (usually two) p=min_p roots into one hierarchy.
  const root = d3.hierarchy({ idx: -1, children: rootIdxs.map(toTree) });

  // Layout: each node gets a vertical block of N rows; depth spreads horizontally.
  const rowPx = 15, colPx = 210, half = ((N - 1) / 2) * rowPx;
  const blockPx = (N + 1.5) * rowPx;
  d3.cluster().nodeSize([blockPx, colPx]).separation(() => 1)(root);

  const reals = root.descendants().filter((d) => d.data.idx >= 0);
  const xs = reals.map((d) => d.x);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const margin = { top: 42, right: 170, bottom: 20, left: 30 };
  const offsetY = margin.top + half + rowPx - minX;      // header room above top block
  const SX = (d) => margin.left + (d.y - colPx);         // real roots (depth 1) → left
  const SY = (d) => d.x + offsetY;
  const width = margin.left + (lin.max_p - lin.min_p) * colPx + margin.right;
  const height = maxX + offsetY + half + margin.bottom;

  host.innerHTML = "";
  host.style.overflowX = "auto";
  const svg = d3.select(host).append("svg")
    .attr("width", width).attr("height", height)
    .style("font-family", "'IBM Plex Sans', system-ui, sans-serif");

  // parent→child links (skip the synthetic-root links); split arms highlighted.
  const linkGen = d3.linkHorizontal().x(SX).y(SY);
  svg.append("g").attr("fill", "none")
    .selectAll("path")
    .data(root.links().filter((l) => l.source.data.idx >= 0))
    .join("path")
    .attr("d", linkGen)
    .attr("stroke", (l) => (isSplit.has(l.target.data.idx) ? hi : "rgba(120,130,150,0.45)"))
    .attr("stroke-width", (l) => (isSplit.has(l.target.data.idx) ? 2 : 1.2));

  // Senator flows (toggle): thread each senator from its row in column p to its
  // row in p+1. Threads that follow a tree edge (parent→child) bundle along the
  // branch; cross-lineage jumps — which the tree cannot represent — peel off as
  // highlighted crossing lines.
  if (state.cmp.linFlows) {
    const hnode = new Map();
    reals.forEach((d) => hnode.set(d.data.idx, d));
    const memCountOf = (i) => Math.min(nodes[i].members.length, N);
    const rowAbs = (i, r) => {                       // absolute (x,y) of member row r
      const d = hnode.get(i);
      return { x: SX(d), y: SY(d) - ((memCountOf(i) - 1) / 2) * rowPx + r * rowPx };
    };
    const childSet = new Map();
    for (const [s, cs] of childrenOf) childSet.set(s, new Set(cs));
    const posCol = new Map();                        // p -> Map(name -> {idx, r})
    nodes.forEach((n, i) => {
      if (!posCol.has(n.p)) posCol.set(n.p, new Map());
      const m = posCol.get(n.p);
      n.members.slice(0, N).forEach(([name], r) => m.set(name, { idx: i, r }));
    });

    const OUT = 95;                                  // start x past the name text
    const along = [], jump = [];
    for (let pi = 0; pi < lin.ps.length - 1; pi++) {
      const A = posCol.get(lin.ps[pi]), B = posCol.get(lin.ps[pi + 1]);
      if (!A || !B) continue;
      for (const [name, a] of A) {
        const b = B.get(name);
        if (!b) continue;
        const s = rowAbs(a.idx, a.r), t = rowAbs(b.idx, b.r);
        const sx = s.x + OUT, tx = t.x - 4, c = (tx - sx) * 0.5;
        const rec = {
          d: `M${sx},${s.y}C${sx + c},${s.y} ${tx - c},${t.y} ${tx},${t.y}`,
          color: archColor(`arch_${nodes[a.idx].k}`, nodes[a.idx].p),
        };
        ((childSet.get(a.idx) || new Set()).has(b.idx) ? along : jump).push(rec);
      }
    }
    const tg = svg.append("g").attr("fill", "none");
    tg.selectAll("path.along").data(along).join("path")
      .attr("d", (r) => r.d).attr("stroke", (r) => hexToRgba(r.color, 0.28))
      .attr("stroke-width", 1);
    tg.selectAll("path.jump").data(jump).join("path")   // drawn on top
      .attr("d", (r) => r.d).attr("stroke", hexToRgba(hi, 0.9))
      .attr("stroke-width", 1.6);
  }

  // p-axis labels aligned to each column.
  const axis = svg.append("g")
    .attr("fill", "#888").attr("font-size", 11).attr("text-anchor", "start");
  for (let p = lin.min_p; p <= lin.max_p; p++) {
    axis.append("text").attr("x", margin.left + (p - lin.min_p) * colPx)
      .attr("y", 18).text(`p = ${p}`);
  }

  // nodes: marker + ranked senator list, new-vs-inherited marked.
  svg.append("g").selectAll("g").data(reals).join("g")
    .attr("transform", (d) => `translate(${SX(d)},${SY(d)})`)
    .each(function (d) {
      const g = d3.select(this), idx = d.data.idx, nd = nodes[idx];
      const color = archColor(`arch_${nd.k}`, nd.p);
      const parentNames = parentOf.has(idx)
        ? new Set(nodes[parentOf.get(idx)].members.slice(0, N).map((m) => m[0]))
        : null;
      const mem = nd.members.slice(0, N);
      const startY = -((mem.length - 1) / 2) * rowPx;
      g.append("circle").attr("r", 3).attr("fill", color);
      if (isSplit.has(idx)) {
        g.append("text").attr("x", 8).attr("y", startY - rowPx)
          .attr("fill", hi).attr("font-size", 11).attr("font-weight", 600)
          .text(`△ ${emergingOf.get(idx)}`);
      }
      mem.forEach(([name], r) => {
        const isNew = parentNames && !parentNames.has(name);
        g.append("text").attr("x", 8).attr("y", startY + r * rowPx).attr("dy", "0.32em")
          .attr("fill", color).attr("font-size", 10)
          .attr("font-weight", isNew ? 700 : 400)
          .text(isNew ? `+ ${name}` : name);
      });
    });
}

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
  document.getElementById("cmp-p").addEventListener("change", (e) => {
    state.cmp.p = +e.target.value; renderActive();
  });
  document.getElementById("cmp-arch").addEventListener("change", (e) => {
    state.cmp.arch = e.target.value; renderActive();
  });
  document.getElementById("cmp-stat").addEventListener("change", (e) => {
    state.cmp.stat = e.target.value; renderActive();
  });
  document.getElementById("cmp-topN").addEventListener("change", (e) => {
    state.cmp.topN = +e.target.value; renderActive();
  });
  document.getElementById("lineage-topN").addEventListener("change", (e) => {
    state.cmp.linTopN = +e.target.value; renderLineage("cmp-lineage");
  });
  document.getElementById("lineage-flows").addEventListener("change", (e) => {
    state.cmp.linFlows = e.target.checked; renderLineage("cmp-lineage");
  });
  for (const [t, id] of [["map", "tabbtn-map"], ["compare", "tabbtn-compare"], ["dist", "tabbtn-dist"]]) {
    document.getElementById(id).addEventListener("click", () => switchTab(t));
  }

  updateCaption();
  renderActive();
}

init();
