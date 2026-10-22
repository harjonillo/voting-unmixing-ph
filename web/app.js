/* PH voting archetypes — static explorer.
 *
 * Loads the JSON/GeoJSON baked by scripts/build_static.py and draws the three
 * tabs with Plotly.js. No server: dropdowns just re-slice already-fetched data.
 */
"use strict";

const DATA = "./data";
const PLOTLY_CFG = { displayModeBar: false, responsive: true };
// Match the UI fonts (loaded via Google Fonts in build_site.py): Instrument Sans
// for text, IBM Plex Mono for numbers (axis ticks).
const FONT = { family: "'Instrument Sans', system-ui, sans-serif", size: 12, color: "#0b0b0b" };
const MONO = "'IBM Plex Mono', ui-monospace, monospace";
const MAP_VIEW = { style: "white-bg", center: { lon: 122.0, lat: 12.8 }, zoom: 4.6 };

// UI chrome colors (mirror the tokens in styles.css).
const INK = "#0b0b0b", INK_2 = "#52514e", INK_MUTED = "#6b6a65";
const GRID = "#efeee9", ZERO = "#a8a7a0", AXIS_LINE = "#c3c2b7", WHISKER = "#3a3936";
const TICKFONT = { family: MONO, size: 11, color: INK_MUTED };
const HOVERLABEL = { font: { family: FONT.family, size: 12 } };
// Plotly axis defaults for the light, gridded look used across the charts.
const AXIS = {
  gridcolor: GRID, zerolinecolor: ZERO, linecolor: AXIS_LINE,
  tickfont: TICKFONT, automargin: true,
};
const axisTitle = (text) => ({ text, font: { size: 11, color: INK_MUTED }, standoff: 8 });

// ---------------------------------------------------------------- data cache
const _cache = new Map();
async function getJSON(url, init) {
  if (!_cache.has(url)) {
    _cache.set(url, fetch(url, init).then((r) => {
      if (!r.ok) throw new Error(`${url}: ${r.status}`);
      return r.json();
    }));
  }
  return _cache.get(url);
}

// ------------------------------------------------------------------- globals
let MANIFEST = null;
const state = {
  year: null, method: "mvsa", level: "province", weighted: true, topN: 6, tab: "map",
  // range: map color range, "data" (autoscale) | "fixed" (0 to 1, or 0 to 100%).
  map: { quantity: "Archetype abundance", arch: "arch_0", groupBy: "alliance", range: "data" },
  // Loadings x-axis on the map tab: "shared" across archetypes | "own" per chart.
  loadingsAxis: "shared",
  cmp: { p: 5, arch: "arch_0", stat: "mean", topN: 15, groupBy: "party",
    lineageTopN: 8, lineageMetric: "cos12", lineageStat: "min" },
};

// --------------------------------------------------------------------- theme
const archIndex = (c) => parseInt(c.split("_")[1], 10);
const archLabel = (c) => `Archetype ${c.split("_")[1]}`;
const archShort = (c) => `A${c.split("_")[1]}`;
// The baked palette has a fixed slot per archetype index (never cycled); an
// index past its end (p = 7 in the sweep) gets a neutral gray.
const FALLBACK_COLOR = "#8c8b85";
function archColor(archCol) {
  return MANIFEST.theme.categorical[archIndex(archCol)] || FALLBACK_COLOR;
}
function palette(nArch) {
  return Array.from({ length: nArch }, (_, i) => archColor(`arch_${i}`));
}
// Small colored dot that sits beside every archetype's text label.
function dot(color) {
  const s = document.createElement("span");
  s.className = "dot"; s.style.background = color; s.setAttribute("aria-hidden", "true");
  return s;
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
// Mix two "#rrggbb" colors: t = 0 -> a, t = 1 -> b.
function mixHex(a, b, t) {
  const p = (h, k) => parseInt(h.substr(k, 2), 16);
  const c = [1, 3, 5].map((k) => Math.round(p(a, k) + (p(b, k) - p(a, k)) * t));
  return `rgb(${c.join(",")})`;
}
// Signed number with a true minus sign.
const fmtSigned = (v, d) => (v < -1e-12 ? "−" : "") + Math.abs(v).toFixed(d);
// Endmember-extraction method (sidebar): MANIFEST.methods[key] =
// {label, base, years, years_meta}; each method has its own baked data tree.
const methodMeta = () => MANIFEST.methods[state.method];
const methodLabel = () => methodMeta().label;
const yearMeta = (year) => methodMeta().years_meta[year];
function nArchFor(year) {
  return yearMeta(year).n_archetypes;
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
// Per-method data root (MVSA at the top of data/, others in data/<method>/);
// geometry is shared, so geoURL stays on DATA.
const mdata = () => (methodMeta().base ? `${DATA}/${methodMeta().base}` : DATA);
const valuesURL = (year, level) => `${mdata()}/values/${year}_${level}_${wtag()}.json`;
const loadingsURL = (year) => `${mdata()}/loadings/${year}.json`;
const sweepURL = (year, p) => `${mdata()}/sweep/${year}_p${p}.json`;
const lineageURL = (year) => `${mdata()}/lineage/${year}.json`;
const distinctURL = (year) => `${mdata()}/distinctness/${year}.json`;
const orderURL = (year) => `${mdata()}/order_sensitivity/${year}.json`;

// -------------------------------------------------------------- chart helpers
function choropleth(divId, geo, records, colorFn, discrete) {
  // colorFn: record -> number|null (null = leave unit uncolored). Returns the
  // plotted z values (the map tab's HTML legend reads their range).
  const ids = [], z = [], text = [];
  for (const rec of records) {
    const v = colorFn(rec);
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    ids.push(rec.id); z.push(v); text.push(rec.id);
  }
  // Shared compact colorbar (no title, thin, pulled to the right edge so it
  // overlays the ocean rather than reserving a white strip the map could use).
  // Callers may merge their own colorbar config, or pass showscale: false and
  // draw the legend in HTML (the map tab does).
  const { colorbar: cbOverrides, ...traceProps } = discrete;
  const colorbar = {
    thickness: 12, len: 0.85, x: 1, xanchor: "right", y: 0.5, yanchor: "middle",
    tickfont: TICKFONT, outlinewidth: 0,
    ...(cbOverrides || {}),
  };
  const trace = {
    type: "choroplethmap", geojson: geo, featureidkey: "id",
    locations: ids, z, text, marker: { opacity: 0.9, line: { color: "#ffffff", width: 0.4 } },
    hovertemplate: "%{text}<br>%{z}<extra></extra>",
    colorbar, ...traceProps,
  };
  const layout = {
    map: MAP_VIEW, height: 600, margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)", font: FONT, hoverlabel: HOVERLABEL,
  };
  Plotly.react(divId, [trace], layout, PLOTLY_CFG);
  return z;
}

// Overlay for NMF's deterministic NNDSVD-initialized run on the (random-init)
// loadings bars: dark circles joined bar-to-bar by a dotted line, so it reads
// apart from the bars' error whiskers.
const NNDSVD_COLOR = "#1f2937";
const NNDSVD_CAPTION = " Dark dots (dotted line): the deterministic NNDSVD-initialized" +
  " run, archetypes matched to the random-init trials.";

// A "nice" tick step (1, 2, 2.5 or 5 × 10^k) giving at most ~5 intervals.
function niceStep(span) {
  if (!(span > 0)) return 1;
  const base = Math.pow(10, Math.floor(Math.log10(span / 5)));
  for (const m of [1, 2, 2.5, 5, 10]) if (span / (m * base) <= 5) return m * base;
  return 10 * base;
}
// x range for loadings bars: [min(0, min(mean − sd)), max(mean + sd)] (NNDSVD
// dots included), rounded out to a tick step.
function loadingsDomain(rows) {
  let lo = 0, hi = 0;
  for (const r of rows) {
    lo = Math.min(lo, r.v - r.sd, r.nn ?? Infinity);
    hi = Math.max(hi, r.v + r.sd, r.nn ?? -Infinity);
  }
  const st = niceStep(hi - lo);
  return {
    range: [Math.floor(lo / st - 1e-9) * st, Math.ceil(hi / st - 1e-9) * st], dtick: st,
  };
}
// "Dela Rosa, Bato (PDPLBN) [3]" -> name + "PDPLBN [3]" tag for the bar labels.
function splitLabel(label) {
  const party = label.match(/\(([^)]*)\)/);
  const rank = label.match(/\[(\d+)\]/);
  return {
    name: cleanCandidate(label),
    tag: [party ? party[1] : "", rank ? `[${rank[1]}]` : ""].filter(Boolean).join(" "),
  };
}

const LOADINGS_ROW_PX = 22;

function loadingsGrid(divId, payload, arch_cols, topN, opts) {
  // payload: {candidates, mean:{arch:[...]}, std?:{arch:[...]}, nndsvd?:{arch:[...]}}
  // opts: {axis: "shared" | "own" (x range), layout: "stack" | "grid"}
  const { axis = "own", layout = "grid" } = opts || {};
  const host = document.getElementById(divId);
  host.innerHTML = "";
  const wrap = el("div", layout === "stack" ? "plot-stack" : "plot-grid");
  host.appendChild(wrap);

  // Top-N rows per archetype (largest first), then one shared domain if asked.
  const rowsBy = arch_cols.map((c) => {
    const mean = payload.mean[c], std = payload.std ? payload.std[c] : null;
    const nn = payload.nndsvd ? payload.nndsvd[c] : null;
    return payload.candidates
      .map((label, i) => ({ label, v: mean[i], sd: std ? std[i] : 0, nn: nn ? nn[i] : null }))
      .sort((a, b) => b.v - a.v)
      .slice(0, topN);
  });
  const shared = axis === "shared" ? loadingsDomain(rowsBy.flat()) : null;

  arch_cols.forEach((c, k) => {
    const cell = el("div", "plot-cell");
    const head = el("div", "plot-title");
    head.append(dot(archColor(c)), archLabel(c));
    const plot = el("div");
    cell.append(head, plot);
    wrap.appendChild(cell);

    const rows = [...rowsBy[k]].reverse();   // Plotly draws the first y at the bottom
    const dom = shared || loadingsDomain(rows);
    const ys = rows.map((r) => r.label);
    const ticktext = rows.map((r) => {
      const { name, tag } = splitLabel(r.label);
      return tag ? `${name} <span style="color:${INK_MUTED};font-size:11px">${tag}</span>` : name;
    });
    const trace = {
      type: "bar", orientation: "h", x: rows.map((r) => r.v), y: ys,
      marker: { color: archColor(c) },
      customdata: rows.map((r) => [cleanCandidate(r.label), r.sd]),
      hovertemplate: payload.std
        ? "%{customdata[0]}<br>%{x:.3f} ± %{customdata[1]:.3f}<extra></extra>"
        : "%{customdata[0]}<br>%{x:.3f}<extra></extra>",
    };
    if (payload.std) {
      trace.error_x = {
        type: "data", array: rows.map((r) => r.sd), visible: true,
        color: WHISKER, thickness: 1.5, width: 4,
      };
    }
    const traces = [trace];
    if (payload.nndsvd) {
      traces.push({
        type: "scatter", mode: "lines+markers", name: "NNDSVD",
        x: rows.map((r) => r.nn), y: ys,
        line: { color: NNDSVD_COLOR, width: 1.2, dash: "dot" },
        marker: { color: NNDSVD_COLOR, size: 6, line: { color: "#ffffff", width: 1 } },
        hovertemplate: "%{y}<br>NNDSVD %{x:.3f}<extra></extra>",
      });
    }
    Plotly.react(plot, traces, {
      showlegend: false, bargap: 0.45,
      height: LOADINGS_ROW_PX * rows.length + 60,
      margin: { l: 4, r: 10, t: 4, b: 4 },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: FONT, hoverlabel: HOVERLABEL,
      xaxis: {
        ...AXIS, range: dom.range, dtick: dom.dtick, fixedrange: true,
        zeroline: true, zerolinewidth: 1, showline: true,
        title: axisTitle("loading"),
      },
      yaxis: {
        automargin: true, fixedrange: true, tickvals: ys, ticktext,
        tickfont: { size: 13, color: INK }, ticks: "", ticklabelstandoff: 6,
      },
    }, PLOTLY_CFG);
  });
}

// Caption under a loadings card title (error-bar source + NNDSVD overlay).
function loadingsCaption(prefix, payload) {
  return prefix + (payload.std
    ? " Error bars: 1 SD across the sweep's trials at this archetype count."
    : " Run the sweep for this year to add trial-based error bars.") +
    (payload.nndsvd ? NNDSVD_CAPTION : "");
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

// Diverging cell shading for the summed-loading matrix, symmetric around 0.
const DIV_NEG = "#a3302f", DIV_MID = "#f0efec", DIV_POS = "#184f95";

function partylistMixing(plotId, tableId, payload, arch_cols, mode) {
  // payload: {candidates, mean:{arch:[per-candidate loading]},
  //           alliance_list?:[[slate, ...], ...], alliance_detail?:[...]}.
  // mode: "party" (default) | "alliance". Renders the group × archetype matrix
  // into plotId and the candidates table into tableId (each in its own card);
  // their captions go in `${id}-sub`.
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

  const order = [];               // groups in first-seen order
  const sums = new Map();         // group -> {arch_col -> summed loading}
  const members = new Map();      // group -> [[rank, name, extra, others], ...]
  payload.candidates.forEach((name, i) => {
    for (const { group: g, others } of placements(i)) {
      if (!sums.has(g)) { sums.set(g, {}); members.set(g, []); order.push(g); }
      const s = sums.get(g);
      for (const c of arch_cols) s[c] = (s[c] || 0) + payload.mean[c][i];
      // `others`: the candidate's other slates, for the "also in UNA" note.
      members.get(g).push([candRank(name), cleanCandidate(name), extraOf(i), others]);
    }
  });
  // Most prominent group (largest total loading) first.
  const total = (p) => arch_cols.reduce((s, c) => s + (sums.get(p)[c] || 0), 0);
  const groups = order.sort((a, b) => total(b) - total(a));
  const noun = mode === "alliance" ? "alliance" : "party";

  // --- group × archetype matrix of summed loadings. Cells are shaded on a
  // diverging ramp scaled by the table's max |value|, with sqrt easing so small
  // sums still show; text flips to white on dark cells.
  const maxAbs = Math.max(1e-12, ...groups.flatMap((g) => arch_cols.map((c) => Math.abs(sums.get(g)[c] || 0))));
  const digits = maxAbs >= 10 ? 1 : maxAbs >= 1 ? 2 : 3;
  const shade = (v) => {
    const t = Math.max(-1, Math.min(1, v / maxAbs)), m = Math.sqrt(Math.abs(t));
    return { bg: mixHex(DIV_MID, t >= 0 ? DIV_POS : DIV_NEG, m), fg: m > 0.55 ? "#ffffff" : INK };
  };
  document.getElementById(`${plotId}-sub`).textContent =
    `Summed endmember loading of each ${noun}'s candidates per archetype (sums, ` +
    "not correlations). Blue is positive, red negative, gray near zero.";
  const host = document.getElementById(plotId);
  host.innerHTML = "";
  const wrap = el("div", "matrix-wrap");
  const tbl = el("table", "matrix");
  const hr = el("tr");
  hr.appendChild(el("th", "", groupHeader));
  for (const c of arch_cols) {
    const th = el("th"), lab = el("span");
    th.scope = "col"; th.title = archLabel(c);
    lab.append(dot(archColor(c)), archShort(c));
    th.appendChild(lab); hr.appendChild(th);
  }
  tbl.appendChild(el("thead")).appendChild(hr);
  const body = tbl.appendChild(el("tbody"));
  for (const g of groups) {
    const tr = el("tr"), th = el("th", "", g + " ");
    th.scope = "row";
    th.appendChild(el("span", "n", `· ${members.get(g).length}`));
    tr.appendChild(th);
    for (const c of arch_cols) {
      const v = sums.get(g)[c] || 0, { bg, fg } = shade(v);
      const td = el("td", "", fmtSigned(v, digits));
      td.style.background = bg; td.style.color = fg;
      td.title = `${g} · ${archLabel(c)}: summed loading ${v.toFixed(3)}`;
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  wrap.appendChild(tbl);
  const key = el("div", "matrix-key");
  const bar = el("div", "bar");
  bar.setAttribute("aria-hidden", "true");
  bar.style.background = `linear-gradient(90deg, ${DIV_NEG}, ${mixHex(DIV_MID, DIV_NEG, 0.5)}, ` +
    `${DIV_MID}, ${mixHex(DIV_MID, DIV_POS, 0.5)}, ${DIV_POS})`;
  key.append(el("span", "", fmtSigned(-maxAbs, digits)), bar,
    el("span", "", "+" + maxAbs.toFixed(digits)), el("span", "label", "summed loading"));
  host.append(wrap, key);

  // --- side table (own card): candidates per group, best-ranked (by election
  // result) first, groups in the matrix's order. Alliance mode lists the *full*
  // slate (so it reads as the coalition's roster); party mode caps at the top 5
  // (parties like IND are large). Each candidate gets its OWN table row — name and
  // its extra column (alliance when grouping by party, party when grouping by
  // alliance) in the same row — so they stay aligned even when either one wraps;
  // the group cell spans its candidates via rowSpan.
  const memberLimit = mode === "alliance" ? Infinity : 5;
  const tableWrap = document.getElementById(tableId);
  const tableCard = tableWrap.closest(".card");
  tableCard.querySelector(".card-title").textContent =
    mode === "alliance" ? "Candidates per alliance" : "Top candidates per party";
  document.getElementById(`${tableId}-sub`).textContent = mode === "alliance"
    ? "Full slate, by election result rank; the extra column shows party."
    : "Top 5 per party, by election result rank; the extra column shows alliance.";
  tableWrap.innerHTML = "";
  tableWrap.className = "roster-wrap";
  const roster = el("table", "roster");
  const rh = el("tr");
  for (const h of [groupHeader, "Candidate", extraHeader]) {
    const th = el("th", "", h); th.scope = "col"; rh.appendChild(th);
  }
  roster.appendChild(el("thead")).appendChild(rh);
  for (const g of groups) {
    const top = members.get(g).sort((a, b) => a[0] - b[0]).slice(0, memberLimit);
    const tbody = el("tbody");
    top.forEach(([rank, name, extra, others], j) => {
      const tr = el("tr");
      if (j === 0) {
        const td = el("td", "group", g);
        td.rowSpan = top.length;
        tr.appendChild(td);
      }
      const tdCand = el("td");
      if (rank !== Infinity) tdCand.append(el("span", "rank", `${rank}.`), " ");
      tdCand.append(name);
      if (others.length) tdCand.append(" ", el("span", "also", `also in ${others.join(", ")}`));
      tr.append(tdCand, el("td", "extra", extra || "—"));
      tbody.appendChild(tr);
    });
    roster.appendChild(tbody);
  }
  tableWrap.appendChild(roster);
}

// --------------------------------------------------------------------- tab: map
// Map legend texts per color-range mode (abundance + turnout maps).
const RANGE_NOTES = {
  data: "Stretched to the lowest and highest value among the units shown. Best for " +
    "spotting variation within one archetype; not comparable across archetypes or years.",
  fixed: "Fixed range. Comparable across archetypes, levels and years; small " +
    "differences may wash out.",
};
const QUANTITY_LABELS = { "Archetype abundance": "Abundance" };

// HTML legend under the map: a gradient bar with lo / mid / hi labels for the
// continuous maps, or one swatch per archetype for the dominant-archetype map.
function mapLegend(kind, cols, lo, hi, fmt) {
  const host = document.getElementById("map-legend");
  host.innerHTML = "";
  if (kind === "Dominant archetype") {
    const sw = el("div", "swatches");
    for (const c of cols) {
      const s = el("span");
      s.append(dot(archColor(c)), archLabel(c));
      sw.appendChild(s);
    }
    host.appendChild(sw);
    return;
  }
  const ramp = el("div", "ramp");
  const bar = el("div", "ramp-bar");
  bar.setAttribute("aria-hidden", "true");
  bar.style.background = `linear-gradient(90deg, ${MANIFEST.theme.sequential.map((s) => s[1]).join(", ")})`;
  const ticks = el("div", "ramp-ticks");
  ticks.append(el("span", "", fmt(lo)), el("span", "", fmt((lo + hi) / 2)), el("span", "", fmt(hi)));
  ramp.append(bar, ticks);
  host.appendChild(ramp);
}

async function renderMap() {
  const year = state.year, level = state.level, nArch = nArchFor(year);
  const [geo, vals, loadings] = await Promise.all([
    getJSON(geoURL(year, level)),
    getJSON(valuesURL(year, level)),
    getJSON(loadingsURL(year)),
  ]);
  const cols = archCols(year);
  const levelLabel = MANIFEST.level_labels[level];
  const unit = levelLabel.toLowerCase();

  // keep the archetype chips valid for this year
  if (!cols.includes(state.map.arch)) state.map.arch = "arch_0";
  const kind = state.map.quantity, sel = state.map.arch;
  fillArchChips(cols, sel);
  document.getElementById("map-arch").hidden = kind !== "Archetype abundance";

  // Color range: autoscaled to the data, or fixed to the quantity's full scale
  // (abundances are fractions, turnout a percentage). Not used by the
  // categorical dominant-archetype map.
  const fixedMax = kind === "Turnout" ? 100 : 1;
  const fixed = state.map.range === "fixed";
  const rangeRow = document.getElementById("map-range-row");
  rangeRow.hidden = kind === "Dominant archetype";
  rangeRow.querySelector('[data-value="fixed"]').textContent =
    kind === "Turnout" ? "Fixed 0 to 100%" : "Fixed 0 to 1";
  const range = fixed ? { zauto: false, zmin: 0, zmax: fixedMax } : { zauto: true };

  let colorFn, discrete, title, lede, fmt;
  if (kind === "Dominant archetype") {
    colorFn = (r) => (r.dominant == null ? null : parseInt(r.dominant, 10) + 0.5);
    discrete = {
      colorscale: discreteScale(palette(nArch)), zmin: 0, zmax: nArch, showscale: false,
      customdata: vals.records.filter((r) => r.dominant != null)
        .map((r) => archLabel(`arch_${r.dominant}`)),
      hovertemplate: "%{text}<br>%{customdata}<extra></extra>",
    };
    title = "Dominant archetype";
    lede = `Archetype with the highest mean abundance in each ${unit}, next to the ` +
      "candidate weights that define every archetype.";
  } else if (kind === "Turnout") {
    colorFn = (r) => (r.turnout == null ? null : r.turnout);
    discrete = {
      colorscale: MANIFEST.theme.sequential, showscale: false, ...range,
      hovertemplate: "%{text}<br>turnout %{z:.1f}%<extra></extra>",
    };
    fmt = (v) => `${v.toFixed(0)}%`;
    title = "Turnout";
    lede = `Voter turnout in each ${unit}, next to the candidate weights that define ` +
      "every archetype.";
  } else {
    colorFn = (r) => (r[sel] == null ? null : r[sel]);
    discrete = {
      colorscale: MANIFEST.theme.sequential, showscale: false, ...range,
      hovertemplate: "%{text}<br>abundance %{z:.3f}<extra></extra>",
    };
    fmt = (v) => v.toFixed(2);
    title = `${archLabel(sel)} abundance`;
    lede = `Abundance of the selected archetype in each ${unit}, next to the candidate ` +
      "weights that define every archetype.";
  }
  const z = choropleth("map-plot", geo, vals.records, colorFn, discrete);
  document.getElementById("map-title").textContent = title;
  document.getElementById("map-subtitle").textContent = `${levelLabel} · ${year}`;
  document.getElementById("map-lede").textContent = lede;
  const [lo, hi] = fixed ? [0, fixedMax]
    : z.reduce(([a, b], v) => [Math.min(a, v), Math.max(b, v)], [Infinity, -Infinity]);
  mapLegend(kind, cols, lo, hi, fmt);
  document.getElementById("map-legend-note").textContent = kind === "Dominant archetype"
    ? "No six-color set is fully colorblind-safe; hover a unit to read its archetype."
    : RANGE_NOTES[fixed ? "fixed" : "data"];

  document.getElementById("map-loadings-sub").textContent =
    loadingsCaption(`${methodLabel()}, national level.`, loadings);
  loadingsGrid("map-loadings", loadings, cols, state.topN,
    { axis: state.loadingsAxis, layout: "stack" });

  partylistMixing("map-partylist", "map-partylist-table", loadings, cols,
    state.map.groupBy);
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
  cos12: "cosine (top 12)", cos: "cosine (full)",
  spearman: "Spearman r", wtau: "weighted tau",
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
  const [lin, dist] = await Promise.all([
    getJSON(lineageURL(state.year)).catch(() => null),
    getJSON(distinctURL(state.year)).catch(() => null),
  ]);
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
          ? "rgba(82,81,78,0.5)" : "rgba(82,81,78,0.14)",
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
        ? "rgba(82,81,78,0.95)" : "rgba(107,106,101,0.6)"),
    },
    hovertext: links.map((l) => {
      const s = lin.nodes[l.source], t = lin.nodes[l.target];
      const kind = l.split ? " · split" : l.matched ? " · matched" : "";
      return `p${s.p}·A${s.k} ${s.label} → p${t.p}·A${t.k} ${t.label}${kind}` +
        `<br>cosine (top 12) ${l.sims.cos12} · cosine (full) ${l.sims.cos}` +
        `<br>Spearman r ${l.sims.spearman} · weighted tau ${l.sims.wtau}` +
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
      bordercolor: archColor(`arch_${n.k}`), borderwidth: 1.5, borderpad: 2,
      bgcolor: "rgba(255,255,255,0.85)",
      text: rows.join("<br>"),
      hovertext: `<b>p = ${n.p} · archetype ${n.k}</b><br>` +
        n.top.slice(0, topN).map((t) => `${t.full} — ${t.w}`).join("<br>"),
    };
  });

  // Within-p distinctness readout above each column: the min or mean pairwise
  // distance (0 = identical … 1 = distinct) between the archetypes of a single
  // unmixing run at that p (config seed), under the selected metric — notebook
  // 08's p-sweep scalars, the same numbers as the distinctness line plot.
  for (const p of ps) {
    const d = dist && dist.distinct[p] && dist.distinct[p][metric];
    if (!d) continue;
    annotations.push({
      x: p, xref: "x", y: 1, yref: "paper", yanchor: "bottom", showarrow: false,
      font: { family: FONT.family, size: 9.5, color: INK_MUTED },
      text: `${stat} d = ${d[stat].toFixed(2)}`,
      hovertext: `${stat} pairwise distance between the ${p} archetypes<br>` +
        `of one run at the config seed<br>` +
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

// --------------------------------------------- compare tab: p-choice diagnostics
// Two small charts under the lineage network, driven by the same metric/stat
// selectors:
//  - notebook 08's sweep line plot: min (or mean) pairwise distance between a
//    run's archetypes vs p, one line per metric (distinctness/{year}.json,
//    baked per year by scripts/bake_distinctness.py);
//  - notebook 09's order-sensitivity summary: Hungarian-matched similarity to
//    the reference run under shuffled precinct order (Arm B) vs varying seed
//    (Arm C), boxplots over trials × archetypes (order_sensitivity/{year}.json,
//    baked per year by scripts/bake_order_sensitivity.py).
const ORDER_ARMS = {
  B: { label: "shuffled precinct order", color: "#2a78d6" },
  C: { label: "varying seed", color: "#eb6834" },
};

function diagnosticsNote(divId, msg) {
  const host = document.getElementById(divId);
  Plotly.purge(host);
  host.innerHTML = "";
  const p = document.createElement("p");
  p.className = "muted";
  p.textContent = msg;
  host.appendChild(p);
}

async function renderDiagnostics() {
  const metric = state.cmp.lineageMetric, stat = state.cmp.lineageStat;

  // --- distinctness vs p (nb08) ---
  const dist = await getJSON(distinctURL(state.year)).catch(() => null);
  if (dist) {
    const ps = dist.ps;
    const traces = Object.entries(LINEAGE_METRICS).map(([m, label], k) => ({
      type: "scatter", mode: "lines+markers", name: label,
      x: ps,
      y: ps.map((p) => (dist.distinct[p] && dist.distinct[p][m])
        ? dist.distinct[p][m][stat] : null),
      line: { color: archColor(`arch_${k}`), width: m === metric ? 3 : 1.3 },
      marker: { color: archColor(`arch_${k}`), size: m === metric ? 7 : 5 },
      opacity: m === metric ? 1 : 0.45,
    }));
    Plotly.react("cmp-distinct", traces, {
      height: 330, margin: { l: 50, r: 8, t: 8, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
      hoverlabel: HOVERLABEL,
      xaxis: { ...AXIS, title: axisTitle("number of archetypes p"), tickvals: ps },
      yaxis: { ...AXIS, title: axisTitle(`${stat} pairwise distance`), rangemode: "tozero" },
      legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, xanchor: "left",
        font: { size: 10 } },
    }, PLOTLY_CFG);
  } else {
    diagnosticsNote("cmp-distinct",
      "No distinctness data for this year — run scripts/bake_distinctness.py.");
  }

  // --- precinct-order sensitivity (nb09) ---
  const ord = await getJSON(orderURL(state.year)).catch(() => null);
  if (!ord) {
    diagnosticsNote("cmp-order",
      "No order-sensitivity data for this year — run " +
      "scripts/bake_order_sensitivity.py.");
    return;
  }
  // One box per (p, arm) over the pooled trials × archetypes samples, Tukey
  // style like notebook 09's seaborn boxplot: quartile box, whiskers to the
  // furthest sample within 1.5 × IQR, points beyond drawn as outliers.
  const traces = Object.keys(ORDER_ARMS).map((arm) => {
    const perP = ord.sims[arm][metric];
    return {
      type: "box", name: ORDER_ARMS[arm].label,
      x: ord.ps.flatMap((p, i) => perP[i].map(() => `p = ${p}`)),
      y: perP.flat(),
      boxpoints: "outliers", boxmean: true,
      marker: { color: ORDER_ARMS[arm].color, size: 3, opacity: 0.6 },
      line: { width: 1.2 },
    };
  });
  Plotly.react("cmp-order", traces, {
    boxmode: "group", boxgap: 0.25, boxgroupgap: 0.15,
    height: 330, margin: { l: 50, r: 8, t: 8, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
    hoverlabel: HOVERLABEL,
    xaxis: { ...AXIS, title: axisTitle("number of archetypes p") },
    yaxis: { ...AXIS, title: axisTitle(`matched similarity (${LINEAGE_METRICS[metric]})`) },
    legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, xanchor: "left",
      font: { size: 10 } },
  }, PLOTLY_CFG);
}

// ----------------------------------------------------------------- tab: compare
async function renderCompare() {
  const year = state.year, level = state.level;
  const p = state.cmp.p;
  await renderLineage("cmp-lineage");
  await renderDiagnostics();
  const [geo, sweep] = await Promise.all([
    getJSON(geoURL(year, level)),
    getJSON(sweepURL(year, p)),
  ]);
  const cols = sweep.arch_cols;
  if (!cols.includes(state.cmp.arch)) state.cmp.arch = "arch_0";
  fillSelect("cmp-arch", cols, state.cmp.arch, archLabel);

  const showStd = state.cmp.stat === "std";
  const recs = sweep.levels[level][wtag()][showStd ? "std" : "mean"];
  const sel = state.cmp.arch;
  choropleth("cmp-plot", geo, recs, (r) => (r[sel] == null ? null : r[sel]),
    { colorscale: MANIFEST.theme.sequential });

  const payload = { candidates: sweep.candidates, mean: sweep.loadings_mean,
    std: sweep.loadings_std, nndsvd: sweep.loadings_nndsvd };
  document.getElementById("cmp-loadings-sub").textContent =
    `Mean ± 1 SD over trials at p = ${p}.` + (payload.nndsvd ? NNDSVD_CAPTION : "");
  loadingsGrid("cmp-loadings", payload, cols, state.cmp.topN, { axis: "own", layout: "grid" });

  partylistMixing("cmp-partylist", "cmp-partylist-table",
    { candidates: sweep.candidates, mean: sweep.loadings_mean,
      alliance_list: sweep.alliance_list, alliance_detail: sweep.alliance_detail },
    cols, state.cmp.groupBy);
}

// ------------------------------------------------------------- tab: distributions
async function renderDist() {
  const year = state.year, level = state.level;
  const vals = await getJSON(valuesURL(year, level));
  const cols = archCols(year);
  const host = document.getElementById("dist-plots");
  host.innerHTML = "";
  const grid = el("div", "plot-grid");
  host.appendChild(grid);
  const unit = MANIFEST.level_labels[level].toLowerCase();
  for (const c of cols) {
    const cell = el("div", "plot-cell"), head = el("div", "plot-title"), plot = el("div");
    head.append(dot(archColor(c)), archLabel(c));
    cell.append(head, plot);
    grid.appendChild(cell);
    const x = vals.records.map((r) => r[c]).filter((v) => v != null);
    Plotly.react(plot, [{
      type: "histogram", x, nbinsx: 40, marker: { color: archColor(c) },
    }], {
      height: 260, bargap: 0.05,
      margin: { l: 40, r: 8, t: 4, b: 30 }, paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)", font: FONT, hoverlabel: HOVERLABEL,
      xaxis: { ...AXIS, title: axisTitle("abundance") },
      yaxis: { ...AXIS, title: axisTitle(`# ${unit}s`) },
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

// Sidebar run summary for the selected year + method (manifest years_meta).
function renderSummary() {
  const m = yearMeta(state.year);
  const rows = [
    ["Archetypes", `p = ${m.n_archetypes}`],
    ["HySime k", m.hysime_kf ?? "—"],
    ["Candidates", m.candidate_labels.length],
    ["RMSE", m.rmse == null ? "—" : m.rmse.toFixed(4)],
  ];
  const host = document.getElementById("run-summary");
  host.innerHTML = "";
  for (const [k, v] of rows) host.append(el("span", "k", k), el("span", "v", String(v)));
}

// Keep the year and compare-tab p valid for the current method/year (a method
// may lack a year; years differ in their sweep's p range), then refill both.
function syncYearAndP() {
  const years = methodMeta().years;
  if (!years.includes(state.year)) {
    state.year = years.includes(MANIFEST.default_year) ? MANIFEST.default_year : years[0];
  }
  fillSeg("year", [...years].sort().map((y) => [y, y]), state.year);
  const ps = yearMeta(state.year).sweep_ps;
  if (ps.length && !ps.includes(state.cmp.p)) {
    // nearest available p
    state.cmp.p = ps.reduce((a, b) =>
      Math.abs(b - state.cmp.p) < Math.abs(a - state.cmp.p) ? b : a);
  }
  fillSelect("cmp-p", ps, state.cmp.p);
}

// --------------------------------------------------------------------- controls
function fillSelect(id, options, value, labelFn) {
  const sel = document.getElementById(id);
  sel.innerHTML = "";
  for (const o of options) {
    const opt = document.createElement("option");
    opt.value = o; opt.textContent = labelFn ? labelFn(o) : o;
    if (String(o) === String(value)) opt.selected = true;
    sel.appendChild(opt);
  }
}

// Segmented controls: a group of .seg buttons, the pressed one marked .on.
function markSeg(id, value) {
  for (const b of document.getElementById(id).querySelectorAll("button")) {
    const on = b.dataset.value === String(value);
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
  }
}
// Replace the group's buttons with `options` ([value, text] pairs).
function fillSeg(id, options, value) {
  const host = document.getElementById(id);
  host.innerHTML = "";
  for (const [v, text] of options) {
    const b = el("button", "seg", text);
    b.type = "button"; b.dataset.value = v;
    host.appendChild(b);
  }
  markSeg(id, value);
}
// Call onPick(value) when an unpressed button is clicked, then mark it.
function wireSeg(id, onPick) {
  document.getElementById(id).addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b || b.classList.contains("on")) return;
    markSeg(id, b.dataset.value);
    onPick(b.dataset.value);
  });
}

// Archetype chips (color dot + "A0" …) on the map tab.
function fillArchChips(cols, value) {
  const host = document.getElementById("map-arch");
  host.innerHTML = "";
  for (const c of cols) {
    const b = el("button", "chip");
    b.type = "button"; b.dataset.value = c;
    b.setAttribute("aria-label", archLabel(c));
    b.append(dot(archColor(c)), archShort(c));
    host.appendChild(b);
  }
  for (const b of host.children) {
    const on = b.dataset.value === value;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
  }
}

function switchTab(tab) {
  state.tab = tab;
  for (const t of ["map", "compare", "dist"]) {
    const btn = document.getElementById(`tabbtn-${t}`);
    document.getElementById(`tab-${t}`).hidden = t !== tab;
    btn.classList.toggle("on", t === tab);
    btn.setAttribute("aria-selected", String(t === tab));
  }
  renderActive();
}

// The sticky sidebar sits below the sticky header: keep --header-h current.
function trackHeaderHeight() {
  const header = document.querySelector(".app-header");
  const set = () => document.documentElement.style.setProperty(
    "--header-h", `${header.getBoundingClientRect().height}px`);
  new ResizeObserver(set).observe(header);
  set();
}

function setTopN(n) {
  state.topN = Math.min(15, Math.max(3, Math.round(n) || 6));
  document.getElementById("topN").value = state.topN;
  if (state.tab === "map") renderActive();
}

// ------------------------------------------------------------------------- init
async function init() {
  trackHeaderHeight();
  // always revalidate: the manifest describes the data tree app.js expects
  MANIFEST = await getJSON(`${DATA}/manifest.json`, { cache: "no-cache" });
  state.year = MANIFEST.default_year;
  state.method = MANIFEST.default_method;

  // only the methods actually baked (e.g. NMF absent until its pipeline runs)
  fillSeg("method", Object.keys(MANIFEST.methods).map((m) => [m, MANIFEST.methods[m].label]),
    state.method);
  syncYearAndP();

  // level radio
  const levels = document.getElementById("levels");
  levels.innerHTML = "";
  for (const lvl of MANIFEST.levels) {
    const lab = el("label");
    const r = document.createElement("input");
    r.type = "radio"; r.name = "level"; r.value = lvl;
    r.checked = lvl === state.level;
    r.addEventListener("change", () => { state.level = lvl; renderActive(); });
    lab.append(r, MANIFEST.level_labels[lvl]);
    levels.appendChild(lab);
  }

  fillSeg("map-quantity",
    MANIFEST.value_kinds.map((k) => [k, QUANTITY_LABELS[k] || k]), state.map.quantity);
  markSeg("map-range", state.map.range);
  markSeg("map-axis", state.loadingsAxis);
  markSeg("map-groupby", state.map.groupBy);
  markSeg("cmp-groupby", state.cmp.groupBy);
  document.getElementById("topN").value = state.topN;

  // wire controls
  wireSeg("year", (v) => {
    state.year = v;
    syncYearAndP(); renderSummary(); renderActive();
  });
  wireSeg("method", (v) => {
    state.method = v;
    syncYearAndP(); renderSummary(); renderActive();
  });
  document.getElementById("topN").addEventListener("change", (e) => setTopN(+e.target.value));
  document.getElementById("topN-dec").addEventListener("click", () => setTopN(state.topN - 1));
  document.getElementById("topN-inc").addEventListener("click", () => setTopN(state.topN + 1));
  document.getElementById("weighted").addEventListener("change", (e) => {
    state.weighted = e.target.checked; renderActive();
  });
  wireSeg("map-quantity", (v) => { state.map.quantity = v; renderActive(); });
  document.getElementById("map-arch").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b || b.dataset.value === state.map.arch) return;
    state.map.arch = b.dataset.value; renderActive();
  });
  wireSeg("map-range", (v) => { state.map.range = v; renderActive(); });
  wireSeg("map-axis", (v) => { state.loadingsAxis = v; renderActive(); });
  wireSeg("map-groupby", (v) => { state.map.groupBy = v; renderActive(); });
  document.getElementById("cmp-p").addEventListener("change", (e) => {
    state.cmp.p = +e.target.value; renderActive();
  });
  document.getElementById("cmp-arch").addEventListener("change", (e) => {
    state.cmp.arch = e.target.value; renderActive();
  });
  document.getElementById("cmp-stat").addEventListener("change", (e) => {
    state.cmp.stat = e.target.value; renderActive();
  });
  wireSeg("cmp-groupby", (v) => { state.cmp.groupBy = v; renderActive(); });
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
    if (state.tab === "compare") { renderLineage("cmp-lineage"); renderDiagnostics(); }
  });
  document.getElementById("cmp-lineage-stat").addEventListener("change", (e) => {
    state.cmp.lineageStat = e.target.value;
    if (state.tab === "compare") { renderLineage("cmp-lineage"); renderDiagnostics(); }
  });
  for (const t of ["map", "compare", "dist"]) {
    document.getElementById(`tabbtn-${t}`).addEventListener("click", () => switchTab(t));
  }

  renderSummary();
  renderActive();
}

init();
