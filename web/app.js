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
  cmp: { p: 5, arch: "arch_0", stat: "mean", topN: 15, groupBy: "party" },
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

function partylistMixing(plotId, tableId, payload, arch_cols, nArch, title, mode) {
  // payload: {candidates, mean:{arch:[per-candidate loading]},
  //           alliance_group?:[...], alliance_detail?:[...]}.
  // mode: "party" (default) | "alliance". Renders the grouped-bar chart into
  // plotId and the top-candidates table into tableId (each in its own card).
  mode = mode === "alliance" ? "alliance" : "party";
  const hasAlliance = Array.isArray(payload.alliance_group);
  // Per-candidate grouping key, and the value shown in the table's extra column.
  const groupOf = (i) => mode === "alliance"
    ? (hasAlliance ? payload.alliance_group[i] : "n/a")
    : extractParty(payload.candidates[i]);
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
  const members = new Map();      // group -> [[rank, cleanName, extra], ...]
  payload.candidates.forEach((name, i) => {
    const g = groupOf(i);
    if (!sums.has(g)) { sums.set(g, {}); members.set(g, []); order.push(g); }
    const s = sums.get(g);
    for (const c of arch_cols) s[c] = (s[c] || 0) + payload.mean[c][i];
    members.get(g).push([candRank(name), cleanCandidate(name), extraOf(i)]);
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

  // Side table (own card): top-5 best-ranked (by election result) candidates per
  // group, groups ordered by total loading (most prominent first). The extra
  // column shows the other dimension (alliance when grouping by party, and party
  // when grouping by alliance), one line per candidate, aligned with the names.
  const tableWrap = document.getElementById(tableId);
  tableWrap.innerHTML = "";
  tableWrap.className = "overflow-y-auto";
  tableWrap.style.maxHeight = height + "px";
  const tbl = document.createElement("table");
  tbl.className = "table table-xs";
  const thead = document.createElement("thead");
  thead.innerHTML =
    `<tr><th>${groupHeader}</th><th>Top candidates (by result rank)</th><th>${extraHeader}</th></tr>`;
  tbl.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const p of [...groups].reverse()) {   // largest total first
    const top = members.get(p).sort((a, b) => a[0] - b[0]).slice(0, 5);
    const tr = document.createElement("tr");
    const tdGroup = document.createElement("td");
    tdGroup.className = "font-medium align-top whitespace-nowrap";
    tdGroup.textContent = p;
    const tdCands = document.createElement("td");
    tdCands.className = "align-top";
    const tdExtra = document.createElement("td");
    tdExtra.className = "align-top text-xs opacity-70";
    for (const [rank, name, extra] of top) {
      const dc = document.createElement("div");
      dc.textContent = rank === Infinity ? name : `${rank}. ${name}`;
      tdCands.appendChild(dc);
      const de = document.createElement("div");
      de.textContent = extra || "—";
      tdExtra.appendChild(de);
    }
    tr.appendChild(tdGroup); tr.appendChild(tdCands); tr.appendChild(tdExtra);
    tbody.appendChild(tr);
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

// Sankey of how archetypes split as p grows across the whole sweep.
// Independent of p/level/weighting.
async function renderLineage(divId) {
  const host = document.getElementById(divId);
  const lin = await getJSON(lineageURL(state.year)).catch(() => null);
  if (!lin) { host.textContent = ""; return; }
  const hi = MANIFEST.theme.highlight;
  const trace = {
    type: "sankey",
    arrangement: "fixed",
    node: {
      label: lin.nodes.map((n) => `p${n.p}·A${n.k} ${n.label}`),
      x: lin.nodes.map((n) => n.x),
      y: lin.nodes.map((n) => n.y),
      pad: 8, thickness: 12,
      color: lin.nodes.map((n) => hexToRgba(archColor(`arch_${n.k}`, n.p), 0.85)),
    },
    link: {
      source: lin.links.map((l) => l.source),
      target: lin.links.map((l) => l.target),
      // clamp so near-zero-similarity links stay visible as thin ribbons
      value: lin.links.map((l) => Math.max(l.similarity, 0.05)),
      color: lin.links.map((l) =>
        l.split ? hexToRgba(hi, 0.55) : "rgba(100,120,160,0.35)"),
      customdata: lin.links.map((l) => l.similarity),
      hovertemplate: "similarity %{customdata}<extra></extra>",
    },
  };
  Plotly.react(divId, [trace], {
    height: 480, margin: { l: 10, r: 10, t: 10, b: 10 },
    paper_bgcolor: "rgba(0,0,0,0)", font: FONT,
  }, PLOTLY_CFG);
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

  const cgb = state.cmp.groupBy;
  partylistMixing("cmp-partylist", "cmp-partylist-table",
    { candidates: sweep.candidates, mean: sweep.loadings_mean,
      alliance_group: sweep.alliance_group, alliance_detail: sweep.alliance_detail },
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
  for (const [t, id] of [["map", "tabbtn-map"], ["compare", "tabbtn-compare"], ["dist", "tabbtn-dist"]]) {
    document.getElementById(id).addEventListener("click", () => switchTab(t));
  }

  updateCaption();
  renderActive();
}

init();
