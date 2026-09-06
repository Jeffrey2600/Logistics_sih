/* Dashboard for the NER logistics platform.
   Plain ES modules-free JS on purpose: no build step, so the whole thing is
   static files FastAPI can serve from the same free-tier dyno as the API. */

const API = location.origin;
const MONTHS = [
  ["jan", "January"], ["feb", "February"], ["mar", "March"], ["apr", "April"],
  ["may", "May"], ["jun", "June"], ["jul", "July (peak monsoon)"], ["aug", "August"],
  ["sep", "September"], ["oct", "October"], ["nov", "November"], ["dec", "December"],
];
const MODES = ["road", "rail", "water", "air"];
const MODE_COLOUR = { road: "#4da3ff", rail: "#a371f7", water: "#2dd4bf", air: "#f778ba" };
// Three risk bands with validated colours. Four warm bands failed the
// colour-difference checks outright: "high" and "severe" were 2.3 apart for a
// deutan reader and 8.2 for normal vision, on exactly the two bands a risk map
// exists to separate. Line width carries the same signal as a second channel,
// so the map never depends on hue alone.
const RISK_COLOUR = { low: "#199e70", elevated: "#c98500", severe: "#d03b3b" };
const RISK_LABEL = { low: "Usually open", elevated: "Often disrupted", severe: "Frequently blocked" };
const RISK_WIDTH = { low: 0.6, elevated: 1.0, severe: 1.7 };

// Named trade-offs, so nobody has to reason about three abstract weights.
const PRIORITIES = {
  balanced: { cost: 0.4, time: 0.4, risk: 0.2 },
  cheapest: { cost: 0.85, time: 0.1, risk: 0.05 },
  fastest: { cost: 0.1, time: 0.85, risk: 0.05 },
  reliable: { cost: 0.2, time: 0.25, risk: 0.55 },
};

const state = {
  places: {},
  modes: new Set(MODES),
  riskModes: new Set(MODES),
  candidates: new Set(["KHM", "TWG", "LGL"]),
  segments: [],
};

const $ = (id) => document.getElementById(id);
const fmtH = (h) => (h == null ? "—" : h >= 24 ? `${(h / 24).toFixed(1)} d` : `${h.toFixed(1)} h`);
const fmtRs = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, options) {
  const response = await fetch(API + path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

/* ---------------------------------------------------------------- map ---- */

// A blank local style. The map must draw our own data even when the venue's
// network blocks the tile host - a demo that dies on conference wifi is no
// demo at all - so the basemap is an enhancement layered on top of this.
const BLANK_STYLE = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#0b0f14" } }],
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
};
const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

const map = new maplibregl.Map({
  container: "map",
  style: BLANK_STYLE,
  center: [92.9, 25.9],
  zoom: 6,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl(), "top-right");

let mapReady = false;
const pending = [];
function onMap(fn) { mapReady ? fn() : pending.push(fn); }

// Try to upgrade to the real basemap; keep the blank one if it is unreachable.
fetch(BASEMAP_STYLE, { mode: "cors" })
  .then((r) => (r.ok ? r.json() : Promise.reject(new Error("basemap unavailable"))))
  .then((style) => {
    basemapLoaded = true;
    map.setStyle(style);
    // setStyle drops our sources and layers, so rebuild them from the cache.
    map.once("styledata", addDataLayers);
  })
  .catch(() => { /* blank basemap: our own layers still render */ });

// Place names are drawn as SDF glyphs, which must be fetched from the tile
// host. If that host is unreachable the glyph request fails and takes the
// whole source's tile parse with it, so the circles disappear as well. Labels
// are therefore added only once a basemap has actually loaded.
let basemapLoaded = false;

function addPlaceLabels() {
  if (map.getLayer("places-label")) return;
  map.addLayer({
    id: "places-label", type: "symbol", source: "places",
    layout: {
      "text-field": ["get", "name"], "text-size": 11,
      "text-offset": [0, 1.2], "text-anchor": "top",
      "text-font": ["Noto Sans Regular"],
      "text-optional": true,
    },
    paint: { "text-color": "#3a4652", "text-halo-color": "#ffffff", "text-halo-width": 1.4 },
  });
}

const EMPTY = { type: "FeatureCollection", features: [] };
const dataCache = { segments: EMPTY, places: EMPTY, route: EMPTY };
let handlersBound = false;

function addDataLayers() {
  for (const id of ["segments", "places", "route"]) {
    if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: dataCache[id] });
  }
  if (!map.getLayer("segments-line")) map.addLayer({
    id: "segments-line", type: "line", source: "segments",
    layout: { "line-cap": "round" },
    paint: {
      "line-color": ["get", "colour"],
      // `zoom` is only valid as the direct input of a top-level interpolate, so
      // the per-feature width scale multiplies each stop's output instead.
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        5, ["*", 1.6, ["coalesce", ["get", "widthScale"], 1]],
        10, ["*", 4.5, ["coalesce", ["get", "widthScale"], 1]],
      ],
      "line-opacity": 0.85,
    },
  });
  // line-dasharray is not data-driven in MapLibre, so surface and air legs are
  // two layers over the same source rather than one expression.
  const routePaint = {
    "line-color": ["get", "colour"],
    "line-width": ["interpolate", ["linear"], ["zoom"], 5, 4, 10, 9],
  };
  if (!map.getLayer("route-line")) map.addLayer({
    id: "route-line", type: "line", source: "route",
    filter: ["!=", ["get", "mode"], "air"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: routePaint,
  });
  if (!map.getLayer("route-line-air")) map.addLayer({
    id: "route-line-air", type: "line", source: "route",
    filter: ["==", ["get", "mode"], "air"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { ...routePaint, "line-dasharray": [2, 1.5] },
  });
  if (!map.getLayer("places-circle")) map.addLayer({
    id: "places-circle", type: "circle", source: "places",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 1.8, 7, 3, 10, 6, 13, 9],
      "circle-color": ["get", "colour"],
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 5, 0.3, 10, 1.5],
      "circle-stroke-color": "#0f1419",
    },
  });
  if (basemapLoaded) addPlaceLabels();

  if (handlersBound) { mapReady = true; pending.splice(0).forEach((fn) => fn()); return; }
  handlersBound = true;

  for (const layer of ["segments-line", "places-circle"]) {
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
    map.on("click", layer, (event) => {
      const props = event.features[0].properties;
      new maplibregl.Popup({ closeButton: false })
        .setLngLat(event.lngLat).setHTML(props.popup).addTo(map);
    });
  }

  mapReady = true;
  pending.splice(0).forEach((fn) => fn());
}

map.on("load", addDataLayers);

// Missing tiles, sprites and glyphs are survivable offline. Anything else is a
// real style or layer fault and must not be swallowed silently.
map.on("error", (event) => {
  const message = (event && event.error && event.error.message) || "";
  if (/tile|sprite|glyph|font|Failed to fetch|NetworkError/i.test(message)) return;
  console.error("map error:", message || event);
});

function setSource(id, features) {
  dataCache[id] = { type: "FeatureCollection", features };
  onMap(() => map.getSource(id) && map.getSource(id).setData(dataCache[id]));
}

function fitTo(coords) {
  if (!coords.length) return;
  onMap(() => {
    const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
    map.fitBounds(bounds, { padding: 90, maxZoom: 9, duration: 700 });
  });
}

function legend(title, rows, note) {
  $("legend").innerHTML =
    `<strong>${esc(title)}</strong>` +
    rows.map(([colour, label]) => `<div><i style="background:${colour}"></i>${esc(label)}</div>`).join("") +
    (note ? `<span class="legend-note">${esc(note)}</span>` : "");
}

/* ------------------------------------------------------------- startup --- */

function fillSelect(select, options, selected) {
  select.innerHTML = options
    .map(([value, label]) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(label)}</option>`)
    .join("");
}

function chipRow(container, values, set, onChange) {
  container.innerHTML = "";
  for (const [value, label] of values) {
    const chip = document.createElement("button");
    chip.className = "chip" + (set.has(value) ? " on" : "");
    chip.textContent = label;
    chip.onclick = () => {
      set.has(value) ? set.delete(value) : set.add(value);
      if (!set.size) set.add(value);           // never let the filter empty out
      chip.classList.toggle("on", set.has(value));
      onChange && onChange();
    };
    container.appendChild(chip);
  }
}

function buildCandidatePicker(places) {
  const search = $("candidateSearch");
  const list = $("candidateList");
  const chosen = $("candidateChosen");

  const render = () => {
    const q = search.value.trim().toLowerCase();
    // Cap the rendered list: typing narrows it, and nobody scrolls 5,000 rows.
    const matches = places
      .filter((p) => !q || p.name.toLowerCase().includes(q))
      .slice(0, 200);
    list.innerHTML = matches
      .map((p) => `<option value="${esc(p.id)}">${esc(p.name)}${p.state ? " — " + esc(p.state) : ""}</option>`)
      .join("");
    if (!matches.length) list.innerHTML = `<option disabled>No match</option>`;
  };

  const renderChosen = () => {
    chosen.innerHTML = [...state.candidates]
      .map((id) => `<span class="chip on" data-remove="${esc(id)}">${esc(state.places[id]?.name || id)} ✕</span>`)
      .join("") || `<span class="note">None selected</span>`;
    $("candCount").textContent = `${state.candidates.size} selected`;
    chosen.querySelectorAll("[data-remove]").forEach((el) => {
      el.onclick = () => { state.candidates.delete(el.dataset.remove); renderChosen(); };
    });
  };

  search.oninput = render;
  list.ondblclick = list.onchange = () => {
    for (const option of list.selectedOptions) {
      if (!option.disabled) state.candidates.add(option.value);
    }
    renderChosen();
  };

  render();
  renderChosen();
}

async function boot() {
  // Junctions outnumber settlements two to one and cannot be chosen
  // meaningfully - "n4021632273" is not somewhere anyone ships from.
  const { places } = await api("/network/places?settlements_only=true");
  places.forEach((p) => (state.places[p.id] = p));
  const options = places.map((p) => [p.id, `${p.name} — ${p.state}`]);

  fillSelect($("origin"), options, "KHM");
  fillSelect($("destination"), options, "GAU");
  for (const id of ["month", "riskMonth", "accessMonth"]) fillSelect($(id), MONTHS, "jul");

  const modeLabels = MODES.map((m) => [m, m[0].toUpperCase() + m.slice(1)]);
  chipRow($("modeChips"), modeLabels, state.modes);
  chipRow($("riskModeChips"), modeLabels, state.riskModes, drawRisk);
  // A chip per place was fine for 46 seed towns and is a wall of 5,000
  // buttons once real settlements land. A filterable list scales.
  buildCandidatePicker(places);
  applyPriority();
  applyCargo();

  planRoute();
}

// The closure list is built from segments the risk tab has already fetched, so
// the route tab no longer pulls megabytes of geometry at boot just to fill a
// dropdown. It is limited to named national highways: an OSM network has
// thousands of unnamed residential stubs, and a planner closes NH-10, not
// "n4021632273 – n12296272662".
function refreshClosureOptions() {
  const closable = state.segments
    .filter((s) => s.mode === "road" && s.named && /^NH/i.test(s.route_ref))
    .sort((a, b) => b.risk.probability - a.risk.probability)
    .slice(0, 300)
    .map((s) => [s.id, `Close ${s.route_ref}: ${s.label}`]);

  const current = $("closure").value;
  fillSelect($("closure"), [["", "No closures"]].concat(closable), current);
}

/* --------------------------------------------------------------- route --- */

function weights() {
  return { cost: +$("wCost").value, time: +$("wTime").value, risk: +$("wRisk").value };
}

function applyPriority() {
  const preset = PRIORITIES[$("priority").value] || PRIORITIES.balanced;
  for (const [key, value] of Object.entries(preset)) {
    const id = "w" + key[0].toUpperCase() + key.slice(1);
    $(id).value = value;
    $(id + "L").textContent = value.toFixed(2);
  }
}

function applyCargo() {
  $("vot").value = $("cargo").value;
  $("votLabel").textContent = $("cargo").value;
}

async function planRoute() {
  const button = $("planBtn");
  const label = button.dataset.label || (button.dataset.label = button.textContent);
  button.disabled = true;
  button.textContent = "Finding the best route…";
  try {
    const closure = $("closure").value;
    const plan = await api("/routing/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: $("origin").value,
        destination: $("destination").value,
        month: $("month").value,
        modes: [...state.modes],
        weights: weights(),
        value_of_time: +$("vot").value,
        blocked_edge_ids: closure ? [closure] : [],
        alternatives: 3,
      }),
    });
    renderRoute(plan);
  } catch (error) {
    $("routeResult").innerHTML = `<div class="error">${esc(error.message)}</div>`;
    setSource("route", []);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function drawItinerary(itinerary) {
  const features = [];
  const coords = [];
  for (const leg of itinerary.legs) {
    if (leg.type !== "travel") continue;
    const line = [[leg.from_lon, leg.from_lat], [leg.to_lon, leg.to_lat]];
    coords.push(...line);
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: line },
      properties: {
        mode: leg.mode,
        colour: MODE_COLOUR[leg.mode],
        popup: `<strong>${esc(leg.from_name)} → ${esc(leg.to_name)}</strong><br>
                ${esc(leg.mode)} · ${esc(leg.route_ref)} · ${leg.distance_km} km<br>
                ${fmtH(leg.hours)} · ${fmtRs(leg.cost_per_tonne)}/t<br>
                risk <b style="color:${RISK_COLOUR[leg.risk.band]}">${esc(leg.risk.band)}</b>`,
      },
    });
  }
  setSource("route", features);
  fitTo(coords);
  legend("How the freight travels", MODES.map((m) => [MODE_COLOUR[m], {
    road: "By road", rail: "By rail", water: "By river barge", air: "By air",
  }[m]]), "A change of colour is a transhipment: unloading and reloading costs time and money.");
}

function renderRoute(plan) {
  const s = plan.recommended.summary;
  drawItinerary(plan.recommended);

  const legs = plan.recommended.legs.map((leg) => {
    if (leg.type === "transfer") {
      return `<div class="leg transfer">
        <div class="where">Transhipment at ${esc(leg.at_name)}</div>
        <div class="meta">${esc(leg.from_mode)} → ${esc(leg.to_mode)} · ${fmtH(leg.hours)} · ${fmtRs(leg.cost_per_tonne)}/t</div>
      </div>`;
    }
    return `<div class="leg mode-${esc(leg.mode)}">
      <div class="where">${esc(leg.from_name)} → ${esc(leg.to_name)}</div>
      <div class="meta">${esc(leg.mode)} · ${esc(leg.route_ref)} · ${leg.distance_km} km · ${fmtH(leg.hours)}
        <span class="badge ${esc(leg.risk.band)}">${esc(leg.risk.band)}</span></div>
    </div>`;
  }).join("");

  const alternatives = plan.alternatives.map((alt, index) => {
    const a = alt.summary;
    return `<div class="alt" data-alt="${index}">
      <strong>${esc(a.mode_chain.join(" → "))}</strong>
      <div class="meta">${fmtH(a.total_hours)} · ${fmtRs(a.cost_per_tonne)}/t · ${a.transhipments} transhipment(s)</div>
    </div>`;
  }).join("");

  $("routeResult").innerHTML = `
    <div class="stats">
      <div class="stat"><b>${fmtH(s.total_hours)}</b><span>door to door</span></div>
      <div class="stat"><b>${fmtRs(s.cost_per_tonne)}</b><span>freight per tonne</span></div>
      <div class="stat"><b>${s.distance_km} km</b><span>distance travelled</span></div>
      <div class="stat"><b>${fmtH(s.expected_delay_hours)}</b><span>likely delay</span></div>
    </div>
    <h2>The journey</h2>${legs}
    ${alternatives ? `<h2 style="margin-top:16px">Other ways to do it</h2>
       <p class="hint">Click one to draw it on the map.</p>${alternatives}` : ""}
    <p class="note">"Likely delay" is the time this shipment can expect to lose to
       landslides and washouts in ${esc(plan.month)}, already included in the
       door-to-door figure.</p>`;

  document.querySelectorAll(".alt").forEach((element) => {
    element.onclick = () => drawItinerary(plan.alternatives[+element.dataset.alt]);
  });
}

/* ----------------------------------------------------------- risk map ---- */

async function drawRisk() {
  setSource("route", []);
  const data = await api(`/network/segments?month=${$("riskMonth").value}`);
  const { segments, risk_model } = data;
  state.segments = segments;
  refreshClosureOptions();
  const shown = segments.filter((s) => state.riskModes.has(s.mode));

  setSource("segments", shown.map((s) => ({
    type: "Feature",
    geometry: { type: "LineString", coordinates: s.geometry },
    properties: {
      colour: RISK_COLOUR[s.risk.band],
      widthScale: RISK_WIDTH[s.risk.band] ?? 1,
      popup: `<strong>${esc(s.label)}</strong><br>
              ${esc(s.mode)} · ${esc(s.route_ref)} · ${esc(s.terrain)} · ${s.distance_km} km<br>
              <b>${esc(RISK_LABEL[s.risk.band] || s.risk.band)}</b> —
              about a ${(s.risk.probability * 100).toFixed(0)}% chance of being
              disrupted somewhere along it this month`,
    },
  })));
  setSource("places", []);
  legend(
    "Chance of being blocked this month",
    Object.entries(RISK_COLOUR).map(([band, colour]) => [colour, RISK_LABEL[band]]),
    "Thicker lines are more likely to close, so the map still reads without colour.",
  );
  fitTo(shown.flatMap((s) => s.geometry));

  // Prefer segments a reader can place on a map: an unnamed junction pair is
  // a true finding but an unusable one.
  const worst = shown.filter((s) => s.named).slice(0, 12).map((s) => `<tr>
      <td>${esc(s.label)}</td>
      <td>${esc(s.route_ref)}</td>
      <td><span class="badge ${esc(s.risk.band)}" title="${esc(RISK_LABEL[s.risk.band] || "")}">${(s.risk.probability * 100).toFixed(0)}%</span></td>
    </tr>`).join("");

  const history = data.landslide_history || { segments: 0, total: 1 };
  const covered = history.segments / Math.max(history.total, 1);
  const historyNote = covered > 0.05
    ? "Estimated from terrain, past landslides on that stretch, how narrow the road is, and how much rain falls there."
    : "Estimated from terrain, road width and rainfall. We have no record of past "
      + "landslides on these roads, so the real risk on the worst stretches is "
      + "probably higher than shown.";

  $("riskResult").innerHTML = `
    <table><thead><tr><th>Segment</th><th>Route</th><th>Risk</th></tr></thead>
    <tbody>${worst}</tbody></table>
    <p class="note">Model: ${esc(risk_model)}. ${esc(historyNote)}</p>`;
}

/* ------------------------------------------------------ accessibility ---- */

function rampColour(value, worst, best) {
  // The same three validated colours as the risk map, interpolated. Red-amber-
  // green with four stops failed the colour-difference checks; three stops with
  // a clear lightness step do not.
  const t = Math.max(0, Math.min(1, (value - worst) / (best - worst || 1)));
  const stops = [[208, 59, 59], [201, 133, 0], [25, 158, 112]];
  const scaled = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(scaled));
  const f = scaled - i;
  const mix = stops[i].map((c, k) => Math.round(c + (stops[i + 1][k] - c) * f));
  return `rgb(${mix.join(",")})`;
}

async function drawAccessibility() {
  setSource("route", []);
  const data = await api(`/accessibility/index?month=${$("accessMonth").value}`);
  const metric = $("accessMetric").value;
  const higherIsBetter = metric === "accessibility_score";
  const values = data.places.map((p) => p[metric]).filter((v) => v != null);
  const lo = Math.min(...values), hi = Math.max(...values);

  setSource("segments", []);
  setSource("places", data.places.map((p) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    properties: {
      name: p.name,
      colour: rampColour(p[metric] ?? lo, higherIsBetter ? lo : hi, higherIsBetter ? hi : lo),
      popup: `<strong>${esc(p.name)}</strong>, ${esc(p.state)}<br>
              accessibility score <b>${p.accessibility_score}</b> (${esc(p.tier.replace(/_/g, " "))})<br>
              market ${fmtH(p.hours_to_market)} · cold store ${fmtH(p.hours_to_coldstore)}<br>
              gateway ${fmtH(p.hours_to_gateway)}`,
    },
  })));
  fitTo(data.places.map((p) => [p.lon, p.lat]));
  legend(
    higherIsBetter ? "How well connected" : "Travel time",
    [["rgb(25,158,112)", higherIsBetter ? "Well connected" : "A short trip"],
     ["rgb(201,133,0)", higherIsBetter ? "Getting by" : "Half a day"],
     ["rgb(208,59,59)", higherIsBetter ? "Cut off" : "A day or more"]],
    higherIsBetter
      ? "Blends time to a market, cold store and the national gateway, plus how much worse the monsoon makes it."
      : "Real driving time over the road network, not distance on a map.",
  );

  const rows = data.underserved.map((p) => `<tr class="clickable" data-lon="${p.lon}" data-lat="${p.lat}">
      <td>${esc(p.name)}</td><td>${esc(p.state)}</td>
      <td>${p.accessibility_score}</td><td>${fmtH(p.hours_to_market)}</td>
    </tr>`).join("");

  $("accessResult").innerHTML = `
    <h2 style="margin-top:16px">Worst connected places</h2>
    <p class="hint">Click a row to fly there. Scored out of 100, where 100 is a
       place with a market, cold storage and a gateway all close by.</p>
    <table><thead><tr><th>Place</th><th>State</th><th>Score</th><th>To a market</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="note">Ranking ${data.settlements.toLocaleString("en-IN")} towns and villages.
       ${data.unreachable ? data.unreachable.toLocaleString("en-IN") + " more have no road link at all and cannot be scored." : ""}</p>`;

  document.querySelectorAll("#accessResult tr.clickable").forEach((row) => {
    row.onclick = () => map.flyTo({ center: [+row.dataset.lon, +row.dataset.lat], zoom: 8.5 });
  });
}

/* ------------------------------------------------------------- siting ---- */

async function evaluateSites() {
  const button = $("siteBtn");
  const label = button.dataset.label || (button.dataset.label = button.textContent);
  button.disabled = true;
  button.textContent = "Comparing sites…";
  try {
    const data = await api("/accessibility/facility-impact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_ids: [...state.candidates],
        facility_type: $("facilityType").value,
        month: $("accessMonth").value,
        threshold_hours: +$("threshold").value,
      }),
    });

    setSource("route", []);
    setSource("segments", []);
    const best = Math.max(1, ...data.ranked_sites.map((r) => r.population_newly_covered));
    setSource("places", data.ranked_sites.map((r) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [r.site.lon, r.site.lat] },
      properties: {
        name: r.site.name,
        colour: rampColour(r.population_newly_covered, 0, best),
        popup: `<strong>${esc(r.site.name)}</strong><br>
                brings <b>${r.population_newly_covered.toLocaleString("en-IN")}</b> people
                within ${$("threshold").value} h<br>
                mean regional score ${r.mean_score_before} → ${r.mean_score_after}`,
      },
    })));
    fitTo(data.ranked_sites.map((r) => [r.site.lon, r.site.lat]));
    legend("Population newly covered", [["rgb(46,160,67)", "most"], ["rgb(248,81,73)", "least"]]);

    // Ranked by settlements reached, so that is the leading column. Population
    // is shown next to it with its coverage stated, because OSM records a
    // population for only a minority of settlements.
    const coverage = Math.round((data.population_coverage ?? 0) * 100);
    $("sitingResult").innerHTML = `
      <h2 style="margin-top:16px">Ranked sites</h2>
      <table><thead><tr><th>#</th><th>Site</th><th>Settlements</th><th>People*</th><th>Gain</th></tr></thead>
      <tbody>${data.ranked_sites.map((r, i) => `<tr>
        <td>${i + 1}</td><td>${esc(r.site.name)}</td>
        <td>${r.settlements_newly_covered.toLocaleString("en-IN")}</td>
        <td>${r.population_newly_covered.toLocaleString("en-IN")}</td>
        <td>+${r.mean_score_gain}</td></tr>`).join("")}</tbody></table>
      <p class="note">Ranked by settlements brought within ${data.threshold_hours} h.
         Baseline: ${data.baseline_settlements_covered.toLocaleString("en-IN")} settlements already covered.</p>
      <p class="note">*OSM records a population for only ${coverage}% of settlements,
         so the population column understates reach and is not what the ranking uses.</p>`;
  } catch (error) {
    $("sitingResult").innerHTML = `<div class="error">${esc(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

/* --------------------------------------------------------------- wiring -- */

document.querySelectorAll("nav button").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === button));
    for (const tab of ["route", "risk", "access", "siting"]) {
      $("tab-" + tab).hidden = tab !== button.dataset.tab;
    }
    if (button.dataset.tab === "risk") drawRisk();
    if (button.dataset.tab === "access") drawAccessibility();
    if (button.dataset.tab === "route") planRoute();
  };
});

$("priority").onchange = () => { applyPriority(); planRoute(); };
$("cargo").onchange = () => { applyCargo(); planRoute(); };
$("month").onchange = planRoute;
$("closure").onchange = planRoute;
$("planBtn").onclick = planRoute;
$("siteBtn").onclick = evaluateSites;
$("riskMonth").onchange = drawRisk;
$("accessMonth").onchange = drawAccessibility;
$("accessMetric").onchange = drawAccessibility;
$("vot").oninput = (e) => ($("votLabel").textContent = "₹" + e.target.value);
$("threshold").oninput = (e) => ($("thresholdL").textContent = e.target.value);
for (const key of ["Cost", "Time", "Risk"]) {
  $("w" + key).oninput = (e) => ($("w" + key + "L").textContent = (+e.target.value).toFixed(2));
}

boot().catch((error) => {
  $("routeResult").innerHTML = `<div class="error">Could not reach the API: ${esc(error.message)}</div>`;
});
