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
// Motion (logo, chip dots, loadings bars) is off for prefers-reduced-motion.
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

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
  // p: the sidebar's archetype count (every tab; manifest default_p at start).
  year: null, method: "mvsa", level: "province", weighted: true, topN: 6, tab: "map", p: 4,
  // range: map color range, "data" (autoscale) | "fixed" (0 to 1, or 0 to 100%).
  map: { quantity: "Archetype abundance", arch: "arch_0", groupBy: "alliance", range: "data" },
  // Loadings x-axis on the map tab: "shared" across archetypes | "own" per chart.
  loadingsAxis: "shared",
  // Compare tab: the lineage network and the p-choice diagnostics.
  cmp: { lineageTopN: 3, lineageMetric: "cos", lineageStat: "min" },
  // Distributions tab: histogram x "fixed" (0 to 1) | "own"; y "count" | "share";
  // loadings x-axis "shared" | "own" (as loadingsAxis on the map tab).
  dist: { x: "fixed", y: "count", bins: 20, axis: "shared" },
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
// Sequential map ramp in an archetype's own hue: a pale tint of its color, the
// color itself, then a darker shade (light = low abundance).
function archRamp(archCol) {
  const c = archColor(archCol);
  return [
    [0, mixHex(c, "#ffffff", 0.92)], [0.25, mixHex(c, "#ffffff", 0.6)],
    [0.55, c], [0.8, mixHex(c, "#000000", 0.3)], [1, mixHex(c, "#000000", 0.55)],
  ];
}
// Turnout map ramp: warm grays (the UI chrome's hue), light = low turnout. Not
// a data hue, so turnout never reads as one of the archetypes.
const TURNOUT_RAMP = [
  "#f4f3ef", "#dddcd5", "#c3c2b9", "#a5a49c", "#86857e", "#686761", "#4a4945", "#2b2a28",
].map((c, i, a) => [i / (a.length - 1), c]);
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
    range: [Math.floor(lo / st - 1e-9) * st, Math.ceil(hi / st - 1e-9) * st]
      .map((v) => +v.toFixed(10)), dtick: st,
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

// Top-N candidates per archetype (largest loading first), with SD and the
// NNDSVD value when the payload has them.
// payload: {candidates, mean:{arch:[...]}, std?:{arch:[...]}, nndsvd?:{arch:[...]}}
function loadingsRows(payload, arch_cols, topN) {
  return arch_cols.map((c) => {
    const mean = payload.mean[c], std = payload.std ? payload.std[c] : null;
    const nn = payload.nndsvd ? payload.nndsvd[c] : null;
    return payload.candidates
      .map((label, i) => ({ label, v: mean[i], sd: std ? std[i] : 0, nn: nn ? nn[i] : null }))
      .sort((a, b) => b.v - a.v)
      .slice(0, topN);
  });
}

// One archetype's horizontal loading bars (± 1 SD whiskers, NNDSVD dots) into
// plotEl, on the x domain `dom` ({range, dtick}; see loadingsDomain). `height`
// overrides the default (row height × rows + axis).
function loadingsChart(plotEl, c, topRows, dom, payload, height) {
  // kept for animateLoadingsAxis, which re-ranges the chart without a redraw
  plotEl.classList.add("loadings-plot");
  plotEl._rows = topRows;
  const rows = [...topRows].reverse();   // Plotly draws the first y at the bottom
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
  Plotly.react(plotEl, traces, {
    showlegend: false, bargap: 0.45,
    height: height || LOADINGS_ROW_PX * rows.length + 60,
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
}

// Loadings small multiples, one titled chart per archetype stacked in divId.
// axis: "shared" (one x range over all archetypes) | "own" (per chart).
function loadingsGrid(divId, payload, arch_cols, topN, axis) {
  const host = document.getElementById(divId);
  host.innerHTML = "";
  const wrap = el("div", "plot-stack");
  host.appendChild(wrap);
  const rowsBy = loadingsRows(payload, arch_cols, topN);
  const shared = axis === "shared" ? loadingsDomain(rowsBy.flat()) : null;
  arch_cols.forEach((c, k) => {
    const cell = el("div", "plot-cell");
    const head = el("div", "plot-title");
    head.append(dot(archColor(c)), archLabel(c));
    const plot = el("div");
    cell.append(head, plot);
    wrap.appendChild(cell);
    loadingsChart(plot, c, rowsBy[k], shared || loadingsDomain(rowsBy[k]), payload);
  });
}

// Switch the loadings charts already drawn in hostId to x-axis mode `axis`,
// sliding the bars to the new range over 0.45s instead of redrawing them.
// Returns false when there is nothing to animate (re-render instead).
function animateLoadingsAxis(hostId, axis) {
  const plots = [...document.getElementById(hostId).querySelectorAll(".loadings-plot")];
  if (!plots.length) return false;
  const shared = axis === "shared" ? loadingsDomain(plots.flatMap((p) => p._rows)) : null;
  for (const p of plots) {
    const { range, dtick } = shared || loadingsDomain(p._rows);
    if (REDUCED_MOTION.matches) {
      Plotly.relayout(p, { "xaxis.range": range, "xaxis.dtick": dtick });
      continue;
    }
    // dtick isn't animatable: set it first, then glide the range
    Plotly.relayout(p, { "xaxis.dtick": dtick }).then(() => Plotly.animate(
      p, { layout: { "xaxis.range": range } },
      { transition: { duration: 450, easing: "cubic-out" }, frame: { duration: 450, redraw: false } },
    ));
  }
  return true;
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
  const wrap = el("div", "matrix-wrap scroll");
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
  tableWrap.className = "roster-wrap scroll";
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
// Overview-only quantity (beside the manifest's value_kinds): the per-unit SD
// of the selected archetype's abundance across the sweep's trials.
const SD_KIND = "Abundance SD";
QUANTITY_LABELS[SD_KIND] = "1 SD across trials";
const UNIT_PLURALS = {
  region: "regions", province: "provinces", municipality: "cities / municipalities",
};
const unitPlural = (level) =>
  UNIT_PLURALS[level] || `${MANIFEST.level_labels[level].toLowerCase()}s`;

// HTML legend under a map: a gradient bar with lo / mid / hi labels for the
// continuous maps, or one swatch per archetype for the dominant-archetype map.
function mapLegend(hostId, kind, cols, lo, hi, fmt, colorscale) {
  const host = document.getElementById(hostId);
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
  bar.style.background = `linear-gradient(90deg, ${colorscale.map((s) => s[1]).join(", ")})`;
  const ticks = el("div", "ramp-ticks");
  ticks.append(el("span", "", fmt(lo)), el("span", "", fmt((lo + hi) / 2)), el("span", "", fmt(hi)));
  ramp.append(bar, ticks);
  host.appendChild(ramp);
}

// One map card (ids `${prefix}-plot`, `-title`, `-subtitle`, `-range-row`,
// `-legend`, `-legend-note`; see map_figure in build_site.py). opts:
//   kind: "Archetype abundance" | "Dominant archetype" | "Turnout"
//   colorFn (record -> value|null), cols (for the dominant legend), range:
//   "data" | "fixed", title, subtitle, fmt (legend numbers), hover (template),
//   colorscale (continuous maps; default the theme's sequential ramp).
function renderMapFigure(prefix, geo, records, opts) {
  const { kind, cols, colorFn, title, subtitle } = opts;
  const colorscale = opts.colorscale || MANIFEST.theme.sequential;
  // Color range: autoscaled to the data, or fixed to the quantity's full scale
  // (abundances are fractions, turnout a percentage). Not used by the
  // categorical dominant-archetype map.
  const fixedMax = kind === "Turnout" ? 100 : 1;
  const fixed = opts.range === "fixed";
  const rangeRow = document.getElementById(`${prefix}-range-row`);
  rangeRow.hidden = kind === "Dominant archetype";
  rangeRow.querySelector('[data-value="fixed"]').textContent =
    kind === "Turnout" ? "Fixed 0 to 100%" : "Fixed 0 to 1";
  const range = fixed ? { zauto: false, zmin: 0, zmax: fixedMax } : { zauto: true };

  let discrete;
  if (kind === "Dominant archetype") {
    discrete = {
      colorscale: discreteScale(cols.map(archColor)), zmin: 0, zmax: cols.length,
      showscale: false,
      customdata: records.filter((r) => colorFn(r) != null).map((r) => archLabel(r.dominant)),
      hovertemplate: "%{text}<br>%{customdata}<extra></extra>",
    };
  } else {
    discrete = {
      colorscale, showscale: false, ...range,
      hovertemplate: opts.hover,
    };
  }
  const z = choropleth(`${prefix}-plot`, geo, records, colorFn, discrete);
  document.getElementById(`${prefix}-title`).textContent = title;
  document.getElementById(`${prefix}-subtitle`).textContent = subtitle;
  const [lo, hi] = fixed ? [0, fixedMax]
    : z.reduce(([a, b], v) => [Math.min(a, v), Math.max(b, v)], [Infinity, -Infinity]);
  mapLegend(`${prefix}-legend`, kind, cols, lo, hi, opts.fmt, colorscale);
  document.getElementById(`${prefix}-legend-note`).textContent = kind === "Dominant archetype"
    ? "Not every color pair is colorblind-safe; hover a unit to read its archetype."
    : RANGE_NOTES[fixed ? "fixed" : "data"];
}

// ------------------------------------------- archetypes at the selected p
// The sidebar's p drives every tab: the sweep's trial mean at that p. Its
// archetype k is shown as its lineage slot ("arch_<color_slot>", anchored to the
// archetypes at the manifest's default_p), so an archetype keeps its name and
// color across p and tabs.
function lineageSlots(lin, p) {
  const toSlot = new Map();
  if (lin) for (const n of lin.nodes) if (n.p === p) toSlot.set(`arch_${n.k}`, `arch_${n.color_slot}`);
  return (c) => toSlot.get(c) || c;
}

// Per-unit records (mean abundances keyed by display column, `dominant` as a
// display column, turnout from the main value table), per-unit SDs, the
// loadings payload and the display columns (sorted by slot) for (year, level,
// p). A year without a sweep at p falls back to the main (HySime-k) run.
async function archetypeView(year, level, p) {
  const vals = await getJSON(valuesURL(year, level));
  if (!yearMeta(year).sweep_ps.includes(p)) {
    const records = vals.records.map((r) =>
      ({ ...r, dominant: r.dominant == null ? null : `arch_${r.dominant}` }));
    return { records, std: null, loadings: await getJSON(loadingsURL(year)),
      cols: archCols(year), p: nArchFor(year), fromSweep: false };
  }
  const [sweep, lin] = await Promise.all([
    getJSON(sweepURL(year, p)), getJSON(lineageURL(year)).catch(() => null),
  ]);
  const toSlot = lineageSlots(lin, p);
  const fromSlot = new Map(sweep.arch_cols.map((c) => [toSlot(c), c]));
  const cols = [...fromSlot.keys()].sort((a, b) => archIndex(a) - archIndex(b));
  const rekey = (obj) => obj && Object.fromEntries(cols.map((c) => [c, obj[fromSlot.get(c)]]));
  const rekeyRec = (r) => ({ id: r.id, ...rekey(r) });
  const turnout = new Map(vals.records.map((r) => [r.id, r.turnout]));
  const lv = sweep.levels[level][wtag()];
  const records = lv.mean.map((r) => {
    const o = rekeyRec(r);
    let dom = null;
    for (const c of cols) if (o[c] != null && (dom === null || o[c] > o[dom])) dom = c;
    return { ...o, dominant: dom, turnout: turnout.get(r.id) ?? null };
  });
  const loadings = { candidates: sweep.candidates, mean: rekey(sweep.loadings_mean),
    std: rekey(sweep.loadings_std), nndsvd: rekey(sweep.loadings_nndsvd),
    alliance_list: sweep.alliance_list, alliance_detail: sweep.alliance_detail };
  return { records, std: lv.std.map(rekeyRec), loadings, cols, p, fromSweep: true };
}

async function renderMap() {
  const year = state.year, level = state.level;
  const [geo, { records, std, loadings, cols, p, fromSweep }] = await Promise.all([
    getJSON(geoURL(year, level)), archetypeView(year, level, state.p),
  ]);
  // The SD map needs the sweep's trials (the main-run fallback has none).
  const sdBtn = document.getElementById("map-quantity").querySelector(`[data-value="${SD_KIND}"]`);
  if (sdBtn) sdBtn.hidden = !std;
  if (state.map.quantity === SD_KIND && !std) {
    state.map.quantity = "Archetype abundance";
    markSeg("map-quantity", state.map.quantity);
  }
  const levelLabel = MANIFEST.level_labels[level];
  const unit = levelLabel.toLowerCase();

  // keep the archetype chips valid for this year
  if (!cols.includes(state.map.arch)) state.map.arch = cols[0];
  const kind = state.map.quantity, sel = state.map.arch;
  fillArchChips("map-arch", cols, sel);
  document.getElementById("map-arch").hidden = kind !== "Archetype abundance" && kind !== SD_KIND;

  const fig = { kind, cols, range: state.map.range, subtitle: `${levelLabel} · ${year}` };
  let lede;
  if (kind === "Dominant archetype") {
    Object.assign(fig, {
      colorFn: (r) => (r.dominant == null ? null : cols.indexOf(r.dominant) + 0.5),
      title: "Dominant archetype",
    });
    lede = `Archetype with the highest mean abundance in each ${unit}, next to the ` +
      "candidate weights that define every archetype.";
  } else if (kind === "Turnout") {
    Object.assign(fig, {
      colorFn: (r) => (r.turnout == null ? null : r.turnout),
      hover: "%{text}<br>turnout %{z:.1f}%<extra></extra>",
      fmt: (v) => `${v.toFixed(0)}%`, title: "Turnout", colorscale: TURNOUT_RAMP,
    });
    lede = `Voter turnout in each ${unit}, next to the candidate weights that define ` +
      "every archetype.";
  } else if (kind === SD_KIND) {
    Object.assign(fig, {
      kind: "Archetype abundance",   // drawn like an abundance map
      colorFn: (r) => (r[sel] == null ? null : r[sel]),
      hover: "%{text}<br>SD %{z:.3f}<extra></extra>", colorscale: archRamp(sel),
      fmt: (v) => v.toFixed(3), title: `${archLabel(sel)} abundance, 1 SD across trials`,
    });
    lede = `How much the selected archetype's abundance in each ${unit} varies across ` +
      `the sweep's trials at p = ${p}, next to the candidate weights that define every ` +
      "archetype.";
  } else {
    Object.assign(fig, {
      colorFn: (r) => (r[sel] == null ? null : r[sel]),
      hover: "%{text}<br>abundance %{z:.3f}<extra></extra>", colorscale: archRamp(sel),
      fmt: (v) => v.toFixed(2), title: `${archLabel(sel)} abundance`,
    });
    lede = `Abundance of the selected archetype in each ${unit}, next to the candidate ` +
      "weights that define every archetype.";
  }
  renderMapFigure("map", geo, kind === SD_KIND ? std : records, fig);
  document.getElementById("map-lede").textContent = lede;

  const trials = yearMeta(year).sweep_trials;
  document.getElementById("map-loadings-sub").textContent = fromSweep
    ? `${methodLabel()} at p = ${p}, national level. Mean ± 1 SD over ${trials ?? "the sweep's"} ` +
      "trials." + (loadings.nndsvd ? NNDSVD_CAPTION : "")
    : loadingsCaption(`${methodLabel()}, national level.`, loadings);
  loadingsGrid("map-loadings", loadings, cols, state.topN, state.loadingsAxis);

  partylistMixing("map-partylist", "map-partylist-table", loadings, cols,
    state.map.groupBy);
}

// ------------------------------------------------------------ compare: lineage
// Lineage network: how archetypes persist or split as p grows across the
// sweep, drawn in HTML + SVG at a fixed pixel size (the card scrolls when
// narrow). One column per p; each node is a fixed-width box listing its top
// candidates, bordered in its lineage color (build_static.py's color_slot:
// matched to the Overview run at its p, then carried along matched links).
// Links are Béziers from box to box: matched p -> p+1 solid (width = selected
// similarity), the extra archetype's closest parent dashed, and other pairs at
// or above a floor dotted. Above each column: that p's min/mean pairwise
// distance (0 = identical … 1 = distinct). Independent of p/level/weighting.
const LINEAGE_SIM_FLOOR = 0.35; // hide near-orthogonal unmatched pairs
const LINEAGE_METRICS = {
  cos12: "cosine (top 12)", cos: "cosine (full)",
  spearman: "Spearman r", wtau: "weighted tau",
  rbo: "RBO", jac12: "Jaccard (top 12)",
};
const capitalize = (s) => s[0].toUpperCase() + s.slice(1);
// Node boxes grow with "Candidates per node": the top candidate on line 1, the
// rest two per line below. Widths come from the measured text (all boxes share
// the widest), heights from the line count; spacing grows to keep the gaps.
const LIN = {
  minW: 132, minH: 52, padX: 8, padY: 5, border: 1.5, l1H: 16.7, lineH: 14.4, tagW: 30,
  linkGap: 48, minColGap: 180, top: 64, rowGap: 24, minRowPx: 76, minPlotH: 496,
};
const NAMES_PER_LINE = 2;
const _measureCtx = document.createElement("canvas").getContext("2d");
function textWidth(text, font) {
  _measureCtx.font = font;
  return _measureCtx.measureText(text).width;
}
// Node text lines: [top candidate, "B · C", "D · E", ...].
function nodeLines(names) {
  const lines = [names[0]];
  for (let r = 1; r < names.length; r += NAMES_PER_LINE) {
    lines.push(names.slice(r, r + NAMES_PER_LINE).join(" · "));
  }
  return lines;
}
const SVG_NS = "http://www.w3.org/2000/svg";

async function renderLineage(divId) {
  const host = document.getElementById(divId);
  const [lin, dist] = await Promise.all([
    getJSON(lineageURL(state.year)).catch(() => null),
    getJSON(distinctURL(state.year)).catch(() => null),
  ]);
  host.innerHTML = "";
  if (!lin) { host.appendChild(el("p", "muted", "No sweep lineage for this year.")); return; }
  const topN = state.cmp.lineageTopN;
  const metric = state.cmp.lineageMetric, stat = state.cmp.lineageStat;
  const simOf = (l) => l.sims[metric];
  const ps = lin.ps, hysime = yearMeta(state.year).hysime_kf;
  const anchorP = lin.anchor_p ?? ps[0];

  document.getElementById("cmp-lineage-sub").textContent =
    "One column per p. Each box lists an archetype's top candidates. Color follows " +
    `an archetype across p, matched to the p = ${anchorP} run on the Overview tab. ` +
    `Above each column: ${stat} pairwise distance between that run's archetypes ` +
    "(0 = identical, 1 = distinct).";
  document.getElementById("cmp-lineage-new-label").textContent =
    `No counterpart at p = ${anchorP} (takes the next free color)`;

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

  // Pixel geometry, sized from the node text (fonts must be loaded to measure).
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  const lines = lin.nodes.map((n) => nodeLines(n.top.slice(0, topN).map((t) => t.name)));
  const fontL1 = `600 13.33px ${FONT.family}`, fontL2 = `11.1px ${FONT.family}`;
  const textW = Math.max(...lines.map((ls) => Math.max(
    textWidth(ls[0], fontL1) + LIN.tagW,
    ...ls.slice(1).map((t) => textWidth(t, fontL2)),
  )));
  const nodeW = Math.max(LIN.minW, Math.ceil(textW + 2 * (LIN.padX + LIN.border) + 4));
  const nodeH = (i) => Math.max(LIN.minH, Math.ceil(2 * (LIN.padY + LIN.border) +
    LIN.l1H + (lines[i].length - 1) * LIN.lineH + 1));
  const maxNodeH = Math.max(...lin.nodes.map((_, i) => nodeH(i)));
  const colGap = Math.max(LIN.minColGap, nodeW + LIN.linkGap);
  const padX = nodeW / 2 + 4;
  const maxRows = Math.max(...ps.map((p) => byP.get(p).length));
  const plotH = Math.max(LIN.minPlotH, maxRows * Math.max(LIN.minRowPx, maxNodeH + LIN.rowGap));
  const width = padX * 2 + (ps.length - 1) * colGap;
  const height = LIN.top + plotH + 40;
  const cx = (p) => padX + ps.indexOf(p) * colGap;
  const cy = (i) => LIN.top + y[i] * plotH;
  const fig = el("div", "lineage");
  fig.style.width = `${width}px`; fig.style.height = `${height}px`;
  host.appendChild(fig);

  // Column headers: p and the within-p distinctness readout (notebook 08's
  // p-sweep scalars, as in the distinctness chart); the HySime-k column is inked.
  for (const p of ps) {
    const col = el("div", p === hysime ? "lin-col anchor" : "lin-col");
    col.style.left = `${cx(p) - nodeW / 2}px`; col.style.width = `${nodeW}px`;
    col.appendChild(el("span", "p", `p = ${p}`));
    const d = dist && dist.distinct[p] && dist.distinct[p][metric];
    if (d) {
      const s = el("span", "d", `${stat} d ${d[stat].toFixed(2)}`);
      s.title = `${stat} pairwise distance between the ${p} archetypes of one run at ` +
        `the config seed (${LINEAGE_METRICS[metric]}; 0 = identical, 1 = distinct)`;
      col.appendChild(s);
    }
    fig.appendChild(col);
  }

  // Links (faint first, so the lineage draws on top), then labels on the
  // matched and split links only.
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", width); svg.setAttribute("height", height);
  svg.setAttribute("aria-hidden", "true");
  const kindOf = (l) => (l.split ? 2 : l.matched ? 1 : 0);
  for (const l of [...links].sort((a, b) => kindOf(a) - kindOf(b))) {
    const s = lin.nodes[l.source], t = lin.nodes[l.target];
    const x0 = cx(s.p) + nodeW / 2, y0 = cy(l.source);
    const x1 = cx(t.p) - nodeW / 2, y1 = cy(l.target), xm = (x0 + x1) / 2;
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", `M${x0} ${y0} C${xm} ${y0} ${xm} ${y1} ${x1} ${y1}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke-linecap", "round");
    if (l.split) {
      path.setAttribute("stroke", WHISKER); path.setAttribute("stroke-width", "1.5");
      path.setAttribute("stroke-dasharray", "5 4");
    } else if (l.matched) {
      path.setAttribute("stroke", "rgba(58,57,54,0.42)");
      path.setAttribute("stroke-width", (1 + 5 * Math.max(simOf(l), 0)).toFixed(2));
    } else {
      path.setAttribute("stroke", "#b5b4ad"); path.setAttribute("stroke-width", "1");
      path.setAttribute("stroke-dasharray", "2 4");
    }
    svg.appendChild(path);
    if (l.matched || l.split) {
      const lab = el("span", "lin-label", simOf(l).toFixed(2));
      lab.style.left = `${xm}px`; lab.style.top = `${(y0 + y1) / 2}px`;
      lab.title = `p${s.p}·${s.label} → p${t.p}·${t.label}${l.split ? " · split" : " · matched"}\n` +
        Object.entries(LINEAGE_METRICS).map(([m, name]) => `${name} ${l.sims[m]}`).join(" · ");
      fig.appendChild(lab);
    }
  }
  fig.prepend(svg);

  // Nodes: top candidate (bold) + lineage tag, then the rest two per line.
  lin.nodes.forEach((n, i) => {
    const slot = n.color_slot ?? n.k;
    const box = el("div", "lin-node");
    box.style.left = `${cx(n.p) - nodeW / 2}px`;
    box.style.top = `${Math.round(cy(i) - nodeH(i) / 2)}px`;
    box.style.width = `${nodeW}px`;
    box.style.height = `${nodeH(i)}px`;
    box.style.borderColor = archColor(`arch_${slot}`);
    const l1 = el("span", "l1");
    l1.append(el("span", "", lines[i][0]), el("span", "tag", slot < anchorP ? `A${slot}` : "new"));
    box.appendChild(l1);
    for (const t of lines[i].slice(1)) box.appendChild(el("span", "l2", t));
    box.title = `p = ${n.p} · ${slot < anchorP ? archLabel(`arch_${slot}`) : "new archetype"}\n` +
      n.top.slice(0, topN).map((t) => `${t.full} — ${t.w}`).join("\n");
    fig.appendChild(box);
  });
  fig.appendChild(el("span", "lin-axis", "number of archetypes p"));
}

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
// The arms differ in fill lightness, not hue, so they never read as archetypes.
const ORDER_ARMS = {
  B: { label: "shuffled precinct order", fill: "#6b6a65", median: "#ffffff", dot: WHISKER, dx: -0.17 },
  C: { label: "varying seed", fill: "#ecebe6", median: INK, dot: "#8a8984", dx: 0.17 },
};
// One fixed color per similarity metric (palette slots in LINEAGE_METRICS order),
// so a metric reads the same whichever is selected.
const metricColor = (m) => archColor(`arch_${Object.keys(LINEAGE_METRICS).indexOf(m)}`);

function diagnosticsNote(divId, msg) {
  const host = document.getElementById(divId);
  Plotly.purge(host);
  host.innerHTML = "";
  host.appendChild(el("p", "muted", msg));
}

function median(xs) {
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

async function renderDiagnostics() {
  const metric = state.cmp.lineageMetric, stat = state.cmp.lineageStat;
  const hysime = yearMeta(state.year).hysime_kf;

  // --- distinctness vs p (nb08) ---
  const dist = await getJSON(distinctURL(state.year)).catch(() => null);
  document.getElementById("cmp-distinct-sub").textContent =
    `${capitalize(stat)} pairwise distance between one run's archetypes (config seed). ` +
    "Past the floor, each added archetype mostly duplicates an existing one.";
  const legend = document.getElementById("cmp-distinct-legend");
  legend.innerHTML = "";
  if (dist) {
    const ps = dist.ps;
    const yOf = (m) => ps.map((p) => (dist.distinct[p] && dist.distinct[p][m])
      ? dist.distinct[p][m][stat] : null);
    // Every metric in its own color; the selected one drawn thick, with markers
    // and on top, the others thin and faded.
    const others = Object.keys(LINEAGE_METRICS).filter((m) => m !== metric);
    const traces = others.map((m) => ({
      type: "scatter", mode: "lines", name: LINEAGE_METRICS[m], x: ps, y: yOf(m),
      line: { color: metricColor(m), width: 1.25 }, opacity: 0.55,
      hovertemplate: `${LINEAGE_METRICS[m]}<br>p = %{x}: %{y:.3f}<extra></extra>`,
    }));
    const sel = yOf(metric);
    traces.push({
      type: "scatter", mode: "lines+markers", name: LINEAGE_METRICS[metric], x: ps, y: sel,
      line: { color: metricColor(metric), width: 2.5 },
      marker: { color: metricColor(metric), size: 8, line: { color: "#ffffff", width: 2 } },
      hovertemplate: `${LINEAGE_METRICS[metric]}<br>p = %{x}: %{y:.3f}<extra></extra>`,
    });
    const last = sel.length - 1;
    const annotations = [{
      x: ps[last], y: sel[last], xanchor: "left", xshift: 8, showarrow: false,
      text: `<b>${LINEAGE_METRICS[metric]}</b>`, font: { size: 11, color: INK },
    }];
    const shapes = [];
    if (hysime) {
      shapes.push({
        type: "line", x0: hysime, x1: hysime, yref: "paper", y0: 0, y1: 1,
        line: { color: "#8a8984", width: 1, dash: "dash" },
      });
      annotations.push({
        x: hysime, yref: "paper", y: 1, yanchor: "bottom", showarrow: false,
        text: `HySime k = ${hysime}`, font: { size: 11, color: INK_2 },
      });
    }
    Plotly.react("cmp-distinct", traces, {
      height: 272, margin: { l: 44, r: 96, t: 20, b: 40 }, showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
      hoverlabel: HOVERLABEL, shapes, annotations,
      xaxis: { ...AXIS, title: axisTitle("number of archetypes p"), tickvals: ps,
        showgrid: false, fixedrange: true },
      yaxis: { ...AXIS, range: [0, 1], dtick: 0.25, tickformat: ".2f", fixedrange: true,
        zeroline: false, showline: true },
    }, PLOTLY_CFG);
    for (const m of Object.keys(LINEAGE_METRICS)) {
      const item = el("span", m === metric ? "legend-item on" : "legend-item");
      const sw = el("span", "line-swatch");
      sw.style.height = m === metric ? "2.5px" : "1.5px";
      sw.style.background = metricColor(m);
      item.append(sw, capitalize(LINEAGE_METRICS[m]));
      legend.appendChild(item);
    }
  } else {
    diagnosticsNote("cmp-distinct",
      "No distinctness data for this year — run scripts/bake_distinctness.py.");
  }

  // --- precinct-order sensitivity (nb09) ---
  const ord = await getJSON(orderURL(state.year)).catch(() => null);
  document.getElementById("cmp-order-ylabel").textContent =
    `y: matched similarity, ${LINEAGE_METRICS[metric]}`;
  if (!ord) {
    document.getElementById("cmp-order-sub").textContent = "";
    diagnosticsNote("cmp-order",
      "No order-sensitivity data for this year — run " +
      "scripts/bake_order_sensitivity.py.");
    return;
  }
  document.getElementById("cmp-order-sub").textContent =
    "Matched similarity of each trial's archetypes to the reference run, over " +
    `${ord.n_trials} trials × archetypes. Box = quartiles, whiskers to 1.5 × IQR, ` +
    "diamond = mean.";
  // One box per (p, arm) over the pooled trials × archetypes samples, Tukey
  // style like notebook 09's seaborn boxplot: quartile box, whiskers to the
  // furthest sample within 1.5 × IQR, points beyond drawn as outliers. On a
  // numeric x (p index ± offset) so the median and mean can be overlaid.
  const BOX_W = 0.24;
  const traces = [], shapes = [];
  for (const [arm, a] of Object.entries(ORDER_ARMS)) {
    const perP = ord.sims[arm][metric];
    traces.push({
      type: "box", name: a.label,
      x: ord.ps.flatMap((p, i) => perP[i].map(() => i + a.dx)),
      y: perP.flat(), width: BOX_W,
      boxpoints: "outliers", fillcolor: a.fill,
      line: { color: WHISKER, width: 1 },
      marker: { color: a.dot, size: 4, opacity: 0.8 },
      hoverinfo: "y",
    });
    const means = perP.map((xs) => xs.reduce((s, v) => s + v, 0) / xs.length);
    perP.forEach((xs, i) => {
      const m = median(xs);
      shapes.push({
        type: "line", x0: i + a.dx - BOX_W / 2 + 0.01, x1: i + a.dx + BOX_W / 2 - 0.01,
        y0: m, y1: m, line: { color: a.median, width: 2 },
      });
    });
    traces.push({
      type: "scatter", mode: "markers", name: `${a.label} mean`,
      x: ord.ps.map((_, i) => i + a.dx), y: means,
      marker: { symbol: "diamond", size: 7, color: "#ffffff", line: { color: INK, width: 1 } },
      customdata: ord.ps.map((p) => `p = ${p} · ${a.label}`),
      hovertemplate: "%{customdata}<br>mean %{y:.3f}<extra></extra>",
    });
  }
  Plotly.react("cmp-order", traces, {
    boxmode: "overlay", showlegend: false, shapes,
    height: 272, margin: { l: 44, r: 8, t: 8, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: FONT,
    hoverlabel: HOVERLABEL,
    xaxis: { ...AXIS, tickvals: ord.ps.map((_, i) => i),
      ticktext: ord.ps.map((p) => `p = ${p}`), range: [-0.6, ord.ps.length - 0.4],
      showgrid: false, zeroline: false, fixedrange: true },
    yaxis: { ...AXIS, range: [-0.1, 1.0], tickvals: [0, 0.25, 0.5, 0.75, 1],
      tickformat: ".2f", zeroline: false, fixedrange: true },
  }, PLOTLY_CFG);
}

// ----------------------------------------------------------------- tab: compare

// The compare tab is about choosing p: the sweep-wide lineage and diagnostics
// (the archetypes at the selected p are on the Overview).
async function renderCompare() {
  await renderLineage("cmp-lineage");
  await renderDiagnostics();
}

// ------------------------------------------------------------- tab: distributions
// One card per archetype: a histogram of its per-unit abundances (binned here,
// so all cards share one y-scale) beside its candidate loadings; then every
// archetype as a strip of jittered dots on one 0-to-1 axis with its quartile
// box and median.
let distUnits = null;   // {n, plural} for the sidebar summary

function quantile(sorted, q) {
  const i = (sorted.length - 1) * q, lo = Math.floor(i), hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}
// Deterministic jitter (so a re-render doesn't shuffle the dots).
function jitter(seed) {
  let s = seed % 2147483647 || 1;
  return () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
}

async function renderDist() {
  const year = state.year, level = state.level;
  const { records, cols, loadings } = await archetypeView(year, level, state.p);
  const unit = MANIFEST.level_labels[level].toLowerCase(), plural = unitPlural(level);
  const { x: xMode, y: yMode, bins } = state.dist;

  const series = cols.map((c) => {
    const pts = records.filter((r) => r[c] != null).map((r) => ({ id: r.id, v: r[c] }));
    const sorted = pts.map((d) => d.v).sort((a, b) => a - b);
    let lo = 0, hi = 1;
    if (xMode === "own" && sorted.length) {
      lo = sorted[0]; hi = sorted[sorted.length - 1];
      if (hi - lo < 1e-9) { lo -= 0.01; hi += 0.01; }
    }
    const w = (hi - lo) / bins, counts = new Array(bins).fill(0);
    for (const v of sorted) counts[Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / w)))] += 1;
    return { c, pts, sorted, lo, hi, w, counts };
  });
  distUnits = { n: Math.max(0, ...series.map((s) => s.pts.length)), plural };
  const yOf = (s, k) => (yMode === "share" ? k / Math.max(1, s.pts.length) : k);
  const yMax = Math.max(1e-9, ...series.flatMap((s) => s.counts.map((k) => yOf(s, k))));
  const yStep = niceStep(yMax), yTop = +(Math.ceil(yMax / yStep - 1e-9) * yStep).toFixed(10);

  // Loadings beside each histogram (sidebar Top N; x range shared or per card).
  const rowsBy = loadingsRows(loadings, cols, state.topN);
  const shared = state.dist.axis === "shared" ? loadingsDomain(rowsBy.flat()) : null;
  const pairH = Math.max(200, LOADINGS_ROW_PX * state.topN + 60);

  const host = document.getElementById("dist-plots");
  host.innerHTML = "";
  series.forEach((s, k) => {
    const card = el("figure", "card dist-card"), head = el("figcaption", "plot-title");
    head.append(dot(archColor(s.c)), archLabel(s.c));
    const pair = el("div", "dist-pair");
    const left = el("div"), right = el("div");
    const plot = el("div"), bars = el("div");
    left.append(el("span", "note", `Abundance across ${plural}`), plot);
    right.append(el("span", "note", "Candidate weights"), bars);
    pair.append(left, right);
    card.append(head, pair);
    host.appendChild(card);
    loadingsChart(bars, s.c, rowsBy[k], shared || loadingsDomain(rowsBy[k]), loadings, pairH);
    const med = s.sorted.length ? quantile(s.sorted, 0.5) : null;
    Plotly.react(plot, [{
      type: "bar", x: s.counts.map((_, b) => s.lo + (b + 0.5) * s.w),
      y: s.counts.map((k) => yOf(s, k)), width: s.w,
      marker: { color: archColor(s.c), line: { color: "#ffffff", width: 1 } },
      customdata: s.counts.map((k, b) => [s.lo + b * s.w, s.lo + (b + 1) * s.w, k]),
      hovertemplate: `%{customdata[0]:.3f}–%{customdata[1]:.3f}<br>%{customdata[2]} ${plural}<extra></extra>`,
    }], {
      height: pairH, bargap: 0, margin: { l: 36, r: 8, t: 14, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: FONT, hoverlabel: HOVERLABEL,
      shapes: med == null ? [] : [{
        type: "line", x0: med, x1: med, yref: "paper", y0: 0, y1: 1.04,
        line: { color: INK, width: 1.5, dash: "dash" },
      }],
      annotations: med == null ? [] : [{
        x: med, yref: "paper", y: 1.04, xanchor: "left", yanchor: "middle", xshift: 4,
        showarrow: false, text: "median", font: { size: 11, color: INK }, bgcolor: "#ffffff",
      }],
      xaxis: { ...AXIS, range: [s.lo, s.hi], showgrid: false, zeroline: false, showline: true,
        tickformat: ".2f", fixedrange: true, title: axisTitle("abundance"),
        ...(xMode === "fixed" ? { dtick: 0.25 } : { nticks: 5 }) },
      yaxis: { ...AXIS, range: [0, yTop], dtick: yStep, zeroline: false, fixedrange: true,
        tickformat: yMode === "share" ? ".0%" : "d", gridcolor: "#f1f0ec" },
    }, PLOTLY_CFG);
  });

  // --- all archetypes on one axis
  document.getElementById("dist-strip-sub").textContent =
    `Each dot is one ${unit}. Box = quartiles, line = median. Hover a dot for the ` +
    `${unit} name and value.`;
  const rnd = jitter(7);
  const traces = [], shapes = [];
  series.forEach((s, i) => {
    const yc = -i;
    traces.push({
      type: "scatter", mode: "markers", name: archLabel(s.c),
      x: s.pts.map((d) => d.v), y: s.pts.map(() => yc + (rnd() - 0.5) * 0.5),
      text: s.pts.map((d) => d.id),
      marker: { color: archColor(s.c), size: 5, opacity: 0.75 },
      hovertemplate: `%{text}<br>%{x:.3f}<extra>${archLabel(s.c)}</extra>`,
    });
    if (s.sorted.length) {
      const [q1, q2, q3] = [0.25, 0.5, 0.75].map((q) => quantile(s.sorted, q));
      shapes.push(
        { type: "rect", x0: q1, x1: q3, y0: yc - 0.28, y1: yc + 0.28,
          line: { color: WHISKER, width: 1 }, layer: "above" },
        { type: "line", x0: q2, x1: q2, y0: yc - 0.33, y1: yc + 0.33,
          line: { color: INK, width: 2 }, layer: "above" },
      );
    }
    if (i < series.length - 1) {
      shapes.push({ type: "line", xref: "paper", x0: 0, x1: 1, y0: yc - 0.5, y1: yc - 0.5,
        line: { color: "#f4f3ef", width: 1 }, layer: "below" });
    }
  });
  Plotly.react("dist-strip", traces, {
    height: 40 * series.length + 60, showlegend: false, shapes,
    margin: { l: 8, r: 8, t: 4, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: FONT, hoverlabel: HOVERLABEL, hovermode: "closest",
    xaxis: { ...AXIS, range: [0, 1], dtick: 0.25, tickformat: ".2f", zeroline: false,
      gridcolor: "#f1f0ec", fixedrange: true, title: axisTitle("abundance") },
    yaxis: { range: [-series.length + 0.5, 0.5], fixedrange: true, zeroline: false,
      showgrid: false, automargin: true, ticks: "", ticklabelstandoff: 8,
      tickvals: series.map((_, i) => -i),
      ticktext: series.map((s) =>
        `<span style="color:${archColor(s.c)}">●</span> ${archLabel(s.c)}`),
      tickfont: { size: 13, color: INK } },
  }, PLOTLY_CFG);
}

// ------------------------------------------------------------------- rendering
// Renders empty their containers and refill them. Meanwhile, hold the active
// panel at its current height: otherwise the pane's content briefly shrinks, the
// browser clamps its scroll position to the shorter content, and the view jumps
// toward the top. Overlapping renders (quick clicks) share one hold, released two frames
// after the last one finishes, once the redrawn plots have laid out.
let _heldRenders = 0;
async function holdHeight(render) {
  const panel = document.getElementById(`tab-${state.tab}`);
  if (_heldRenders++ === 0) panel.style.minHeight = `${panel.offsetHeight}px`;
  try {
    return await render();
  } finally {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (--_heldRenders === 0) panel.style.minHeight = "";
    }));
  }
}

async function renderActive() {
  document.getElementById("status").textContent = "Loading…";
  try {
    await holdHeight(async () => {
      if (state.tab === "map") await renderMap();
      else if (state.tab === "compare") await renderCompare();
      else await renderDist();
    });
    renderSummary();
    document.getElementById("status").textContent = "";
  } catch (e) {
    document.getElementById("status").textContent = "Error: " + e.message;
    console.error(e);
  }
}

// Sidebar run summary for the selected year + method (manifest years_meta),
// with the facts relevant to the active tab.
function renderSummary() {
  const m = yearMeta(state.year), ps = m.sweep_ps;
  const onSweep = ps.includes(state.p), p = onSweep ? state.p : m.n_archetypes;
  const rmse = onSweep ? m.sweep_rmse[String(p)] : m.rmse;
  const rows = state.tab === "compare" ? [
    ["Sweep", ps.length ? `p = ${ps[0]} … ${ps[ps.length - 1]}` : "—"],
    ["Trials per p", m.sweep_trials ?? "—"],
    ["HySime k", m.hysime_kf ?? "—"],
  ] : state.tab === "dist" ? [
    ["Archetypes", `p = ${p}`],
    ["Units", distUnits ? `${distUnits.n} ${distUnits.plural}` : "—"],
  ] : [
    ["Archetypes", `p = ${p}`],
    ["HySime k", m.hysime_kf ?? "—"],
    ["Candidates", m.candidate_labels.length],
    [onSweep ? "RMSE (mean)" : "RMSE", rmse == null ? "—" : rmse.toFixed(4)],
  ];
  const host = document.getElementById("run-summary");
  host.innerHTML = "";
  for (const [k, v] of rows) host.append(el("span", "k", k), el("span", "v", String(v)));
}

// Keep the year and the sidebar p valid for the current method/year (a method
// may lack a year; years could differ in their sweep's p range), then refill
// both. Without a sweep the p selector hides and the tabs show the main run.
function syncYearAndP() {
  const years = methodMeta().years;
  if (!years.includes(state.year)) {
    state.year = years.includes(MANIFEST.default_year) ? MANIFEST.default_year : years[0];
  }
  fillSeg("year", [...years].sort().map((y) => [y, y]), state.year);
  const ps = yearMeta(state.year).sweep_ps;
  if (ps.length && !ps.includes(state.p)) {
    // nearest available p
    state.p = ps.reduce((a, b) => Math.abs(b - state.p) < Math.abs(a - state.p) ? b : a);
  }
  fillSeg("p", ps.map((p) => [p, String(p)]), state.p);
  document.getElementById("p").closest(".field").hidden = !ps.length;
}

// --------------------------------------------------------------------- controls
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
    b.type = "button"; b.dataset.value = String(v);
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

// Archetype chips (color dot + "A0" …) on the map and compare tabs.
function fillArchChips(id, cols, value) {
  const host = document.getElementById(id);
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
    // the selected chip is tinted with its archetype color (~14% alpha)
    b.style.background = on ? hexToRgba(archColor(b.dataset.value), 0.14) : "";
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
  // Top N drives the loadings on the overview and distributions tabs.
  document.getElementById("topN-field").hidden = tab === "compare";
  renderSummary();
  renderActive().then(resizeActivePlots);
}

// Plotly's responsive mode follows window resizes only, but the main pane can
// change width on its own (its scrollbar appearing, the shell wrapping): resize
// the active tab's charts with the pane. Hidden tabs can't resize, so a tab
// also resizes its charts when it is shown again.
function resizeActivePlots() {
  for (const gd of document.querySelectorAll(`#tab-${state.tab} .js-plotly-plot`)) {
    Plotly.Plots.resize(gd);
  }
}
function trackPaneWidth() {
  const pane = document.querySelector(".main");
  let width = pane.clientWidth, queued = false;
  new ResizeObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (pane.clientWidth === width) return;
      width = pane.clientWidth;
      resizeActivePlots();
    });
  }).observe(pane);
}

function setTopN(n) {
  state.topN = Math.min(15, Math.max(3, Math.round(n) || 6));
  document.getElementById("topN").value = state.topN;
  if (state.tab !== "compare") renderActive();
}

// ------------------------------------------------------------------------- init
async function init() {
  trackPaneWidth();
  // always revalidate: the manifest describes the data tree app.js expects
  MANIFEST = await getJSON(`${DATA}/manifest.json`, { cache: "no-cache" });
  state.year = MANIFEST.default_year;
  state.method = MANIFEST.default_method;
  state.p = MANIFEST.default_p ?? state.p;

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

  const kinds = [...MANIFEST.value_kinds];
  kinds.splice(kinds.indexOf("Archetype abundance") + 1, 0, SD_KIND);
  fillSeg("map-quantity", kinds.map((k) => [k, QUANTITY_LABELS[k] || k]), state.map.quantity);
  markSeg("map-range", state.map.range);
  markSeg("map-axis", state.loadingsAxis);
  markSeg("map-groupby", state.map.groupBy);
  markSeg("cmp-lineage-stat", state.cmp.lineageStat);
  markSeg("dist-x", state.dist.x);
  markSeg("dist-y", state.dist.y);
  markSeg("dist-axis", state.dist.axis);
  document.getElementById("cmp-lineage-metric").value = state.cmp.lineageMetric;
  document.getElementById("cmp-lineage-topn").value = state.cmp.lineageTopN;
  document.getElementById("dist-bins").value = state.dist.bins;
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
  wireSeg("map-axis", (v) => {
    state.loadingsAxis = v;
    if (!animateLoadingsAxis("map-loadings", v)) renderActive();
  });
  wireSeg("map-groupby", (v) => { state.map.groupBy = v; renderActive(); });
  wireSeg("p", (v) => { state.p = +v; renderSummary(); renderActive(); });
  document.getElementById("cmp-lineage-topn").addEventListener("change", (e) => {
    state.cmp.lineageTopN = Math.min(12, Math.max(2, Math.round(+e.target.value) || 3));
    e.target.value = state.cmp.lineageTopN;
    if (state.tab === "compare") holdHeight(() => renderLineage("cmp-lineage"));
  });
  document.getElementById("cmp-lineage-metric").addEventListener("change", (e) => {
    state.cmp.lineageMetric = e.target.value;
    if (state.tab === "compare") {
      holdHeight(() => Promise.all([renderLineage("cmp-lineage"), renderDiagnostics()]));
    }
  });
  wireSeg("cmp-lineage-stat", (v) => {
    state.cmp.lineageStat = v;
    if (state.tab === "compare") {
      holdHeight(() => Promise.all([renderLineage("cmp-lineage"), renderDiagnostics()]));
    }
  });
  wireSeg("dist-x", (v) => { state.dist.x = v; renderActive(); });
  wireSeg("dist-y", (v) => { state.dist.y = v; renderActive(); });
  wireSeg("dist-axis", (v) => {
    state.dist.axis = v;
    if (!animateLoadingsAxis("dist-plots", v)) renderActive();
  });
  document.getElementById("dist-bins").addEventListener("change", (e) => {
    state.dist.bins = Math.min(60, Math.max(5, Math.round(+e.target.value) || 20));
    e.target.value = state.dist.bins;
    renderActive();
  });
  for (const t of ["map", "compare", "dist"]) {
    document.getElementById(`tabbtn-${t}`).addEventListener("click", () => switchTab(t));
  }

  renderSummary();
  renderActive();
}

init();
