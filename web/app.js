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
  cmp: { p: 5, arch: "arch_0", stat: "mean", topN: 15 },
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

// -------------------------------------------------------------- chart helpers
function choropleth(divId, geo, records, colorFn, colorbarTitle, discrete) {
  // colorFn: record -> number|null (null = leave unit uncolored)
  const ids = [], z = [], text = [];
  for (const rec of records) {
    const v = colorFn(rec);
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    ids.push(rec.id); z.push(v); text.push(rec.id);
  }
  const trace = {
    type: "choroplethmap", geojson: geo, featureidkey: "id",
    locations: ids, z, text, marker: { opacity: 0.9 },
    hovertemplate: "%{text}<br>%{z}<extra></extra>",
    ...discrete,
  };
  const layout = {
    map: MAP_VIEW, height: 640, margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)", font: FONT,
    coloraxis: {},
  };
  if (colorbarTitle) trace.colorbar = { title: { text: colorbarTitle } };
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
      margin: { l: 4, r: 4, t: 34, b: 24 }, paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)", font: FONT, xaxis: { title: { text: "loading" } },
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
  let colorFn, title, discrete;
  if (kind === "Dominant archetype") {
    const colors = palette(nArch);
    colorFn = (r) => (r.dominant == null ? null : parseInt(r.dominant, 10) + 0.5);
    discrete = {
      colorscale: discreteScale(colors), zmin: 0, zmax: nArch,
      colorbar: {
        title: { text: "dominant" }, tickmode: "array",
        tickvals: cols.map((_, i) => i + 0.5), ticktext: cols.map(archLabel),
      },
    };
    title = null;
  } else if (kind === "Turnout") {
    colorFn = (r) => (r.turnout == null ? null : r.turnout);
    discrete = { colorscale: MANIFEST.theme.sequential };
    title = "turnout (%)";
  } else {
    colorFn = (r) => (r[sel] == null ? null : r[sel]);
    discrete = { colorscale: MANIFEST.theme.sequential };
    title = `mean abundance (${archLabel(sel)})`;
  }
  choropleth("map-plot", geo, vals.records, colorFn, title, discrete);

  const cap = loadings.std
    ? "Error bars: std across the sweep's trials at this archetype count."
    : "Run the sweep for this year to add trial-based error bars.";
  loadingsGrid("map-loadings", loadings, cols, nArch, state.topN,
    "Candidate weights per endmember (MVSA, national-level). " + cap);
}

// ----------------------------------------------------------------- tab: compare
async function renderCompare() {
  const year = state.year, level = state.level, nArch = nArchFor(year);
  const p = state.cmp.p;
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
  const stat = showStd ? "std" : "mean";
  choropleth("cmp-plot", geo, recs, (r) => (r[sel] == null ? null : r[sel]),
    `${stat} (${archLabel(sel)})`, { colorscale: MANIFEST.theme.sequential });

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
  for (const [t, id] of [["map", "tabbtn-map"], ["compare", "tabbtn-compare"], ["dist", "tabbtn-dist"]]) {
    document.getElementById(id).addEventListener("click", () => switchTab(t));
  }

  updateCaption();
  renderActive();
}

init();
