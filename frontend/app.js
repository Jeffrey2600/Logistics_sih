/* Dashboard for the NER logistics platform.
   Plain ES modules-free JS on purpose: no build step, so the whole thing is
   static files FastAPI can serve from the same free-tier dyno as the API. */

const API = location.origin;
const MONTH_NAME = {
  jan: "January", feb: "February", mar: "March", apr: "April", may: "May",
  jun: "June", jul: "July", aug: "August", sep: "September", oct: "October",
  nov: "November", dec: "December",
};
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
const RISK_COLOUR = { low: "#1baf7a", elevated: "#eda100", severe: "#d03b3b" };
// Band names now come from the translation table: see "band.*" in i18n.js.
// The server bands the combined figure; the map may be showing one hazard.
const bandOf = (p) => (p < 0.15 ? "low" : p < 0.35 ? "elevated" : "severe");

// A band the palette does not know must never reach MapLibre as undefined: it
// paints those black, which is not in the legend and reads as a fourth
// category. This happened for real when the server's band names changed and a
// browser was still running a cached older script.
function riskColour(band) {
  const colour = RISK_COLOUR[band];
  if (colour) return colour;
  console.warn(`unknown risk band "${band}" - the page and the API disagree; ` +
               "reload with Ctrl+Shift+R");
  return "#9aa4ad";   // neutral grey, visibly "unknown" rather than severe
}

function floodNote(model) {
  if (!model || !model.available) {
    return `<p class="note">Flood risk is not included: elevation data has not
      been built. Run <code>data/ingest/fetch_elevation.py</code>.</p>`;
  }
  const covered = model.elevation_coverage ?? 0;
  if (covered < 0.95) {
    // Silence here would paint the unmeasured half of the valley green.
    return `<p class="note">Flood risk covers only ${(covered * 100).toFixed(0)}%
      of the network — the rest has no elevation yet and is shown as
      landslide risk alone, not as safe.</p>`;
  }
  return `<p class="note">Flood risk from ground elevation, terrain and season.
    ${model.flood_dominated.toLocaleString("en-IN")} of these roads are at more
    risk from flooding than from landslides.</p>`;
}
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
//
// The blank ground is light, not dark. Every other surface here is light, the
// risk palette was validated against a light background, and on a projector a
// dark slab where the basemap should be reads as a broken page rather than as
// a map with no tiles. When the real basemap loads it replaces this anyway.
const BLANK_STYLE = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#eaeef1" } }],
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
};
// Two base maps, both optional enhancements over BLANK_STYLE.
//
// "Map" is the light vector style the risk palette was validated against.
// "Satellite" is Esri's World Imagery, which is what people mean when they ask
// for something that looks like Google Maps. Imagery on its own is pretty and
// useless for choosing a town, so it carries Esri's reference layer on top for
// place names and boundaries. Neither needs an API key.
const BASEMAPS = {
  map: {
    label: "ui.map",
    style: "https://tiles.openfreemap.org/styles/positron",
    probe: "https://tiles.openfreemap.org/styles/positron",
    dark: false,
  },
  satellite: {
    label: "ui.satellite",
    imagery: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    reference: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    probe: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/6/26/45",
    attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
    dark: true,
  },
};
let basemapKind = "map";

// Built locally rather than fetched: a raster style is four lines of JSON, and
// not fetching it is one less thing that can fail on a blocked network.
function satelliteStyle() {
  const sat = BASEMAPS.satellite;
  return {
    version: 8,
    sources: {
      "sat-imagery": {
        type: "raster", tiles: [sat.imagery], tileSize: 256, maxzoom: 19,
        attribution: sat.attribution,
      },
      "sat-reference": {
        type: "raster", tiles: [sat.reference], tileSize: 256, maxzoom: 19,
      },
    },
    layers: [
      // Deep water blue rather than black: while imagery tiles are still
      // loading the gaps read as sea, not as a broken page.
      { id: "bg", type: "background", paint: { "background-color": "#0d1b2a" } },
      { id: "sat-imagery", type: "raster", source: "sat-imagery" },
      { id: "sat-reference", type: "raster", source: "sat-reference" },
    ],
    glyphs: BLANK_STYLE.glyphs,
  };
}

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

// Switching the base map replaces the whole style, which drops our sources and
// layers with it, so they are rebuilt from the cache on the next styledata.
function applyBasemapStyle(kind) {
  const done = () => { basemapLoaded = true; addDataLayers(); };
  if (kind === "satellite") {
    map.setStyle(satelliteStyle());
    map.once("styledata", done);
    return Promise.resolve(true);
  }
  return fetch(BASEMAPS.map.style, { mode: "cors" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("basemap unavailable"))))
    .then((style) => { map.setStyle(style); map.once("styledata", done); return true; })
    .catch(() => false);   // blank ground: our own layers still render
}

function setBasemap(kind) {
  if (!BASEMAPS[kind] || kind === basemapKind) return;
  basemapKind = kind;
  // The class drives the few bits of chrome that have to change over imagery -
  // the legend needs an opaque ground once it is sitting on dark pixels.
  document.body.classList.toggle("satellite", BASEMAPS[kind].dark);
  document.querySelectorAll("#basemapSwitch button").forEach((b) => {
    b.classList.toggle("on", b.dataset.basemap === kind);
  });
  applyBasemapStyle(kind);
}

// Probe each base map the same way the map itself will consume it.
//
// A vector style is fetched and parsed as JSON, so it genuinely needs CORS.
// Raster tiles are loaded as images, which do not - probing those with fetch()
// would report a host unreachable whenever it merely declines a cross-origin
// read, and would hide a base map that works perfectly.
function reachable(config) {
  if (config.style) {
    return fetch(config.probe, { mode: "cors" }).then((r) => r.ok).catch(() => false);
  }
  return new Promise((resolve) => {
    const image = new Image();
    const timer = setTimeout(() => resolve(false), 8000);
    const settle = (ok) => { clearTimeout(timer); resolve(ok); };
    image.onload = () => settle(true);
    image.onerror = () => settle(false);
    image.src = config.probe;
  });
}

// Disable the base maps this network cannot reach, rather than leaving a
// button that silently does nothing when clicked.
function probeBasemaps() {
  Object.entries(BASEMAPS).forEach(([kind, config]) => {
    if (kind === basemapKind) return;
    reachable(config).then((ok) => {
      if (ok) return;
      const button = document.querySelector(`#basemapSwitch button[data-basemap="${kind}"]`);
      if (!button) return;
      button.disabled = true;
      button.title = "This base map is not reachable from this network";
    });
  });
}

applyBasemapStyle("map");

// Place names are drawn as SDF glyphs, which must be fetched from the tile
// host. If that host is unreachable the glyph request fails and takes the
// whole source's tile parse with it, so the circles disappear as well. Labels
// are therefore added only once a basemap has actually loaded.
let basemapLoaded = false;

function addPlaceLabels() {
  if (map.getLayer("places-label")) return;
  map.addLayer({
    id: "places-label", type: "symbol", source: "places",
    minzoom: 7,
    layout: {
      "text-field": ["get", "name"], "text-size": 11,
      "text-offset": [0, 1.2], "text-anchor": "top",
      "text-font": ["Noto Sans Regular"],
      "text-optional": true,
      // Five thousand labels at region zoom is a wall of text. Show the
      // notable places first and the rest only as the reader zooms in.
      "text-allow-overlap": false,
      "text-padding": 4,
    },
    paint: {
      "text-color": "#3a4652", "text-halo-color": "#ffffff", "text-halo-width": 1.4,
    },
  });
  paintPlaceLabels();
}

// Dark-on-light labels vanish over satellite imagery, so the pair is flipped
// with the base map rather than being fixed to the light style.
function paintPlaceLabels() {
  if (!map.getLayer("places-label")) return;
  const dark = BASEMAPS[basemapKind] && BASEMAPS[basemapKind].dark;
  map.setPaintProperty("places-label", "text-color", dark ? "#ffffff" : "#3a4652");
  map.setPaintProperty("places-label", "text-halo-color", dark ? "#11202e" : "#ffffff");
  map.setPaintProperty("places-label", "text-halo-width", dark ? 1.6 : 1.4);
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
    "line-width": [
      "interpolate", ["linear"], ["zoom"],
      5, ["case", ["==", ["get", "chosen"], 1], 5, 2.5],
      10, ["case", ["==", ["get", "chosen"], 1], 10, 5],
    ],
  };
  if (!map.getLayer("route-line")) map.addLayer({
    id: "route-line", type: "line", source: "route",
    filter: ["!=", ["get", "mode"], "air"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      ...routePaint,
      "line-opacity": ["case", ["==", ["get", "chosen"], 1], 1, 0.45],
    },
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
      // A halo that separates overlapping dots without reading as a third
      // colour: on the light basemap a near-black ring looked like a category.
      "circle-stroke-color": "#ffffff",
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

/* ------------------------------------------------- place picker (search) --
 * A <select> with 5,594 options is not a control anyone can use: the list is
 * unscrollable and the browser's own type-ahead only matches from the first
 * letter, so "Guwahati" cannot be found by typing "guw" if the cursor has
 * moved on. This replaces it with a filtered list, and keeps a hidden input of
 * the same id so `$("origin").value` and its change event mean what they did
 * before.
 */
const combos = {};
// A test seam. The picker is a search box now, so a test that wants a specific
// place has to know its name; this is the only way to get from an id to one
// without duplicating the place list in the test file.
window.__combos = combos;

function normalise(text) {
  // Fold accents so "Nawājisnagar" is found by typing "nawajis". OSM names in
  // the region carry diacritics that nobody types.
  return String(text).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function markMatch(label, query) {
  if (!query) return esc(label);
  const at = normalise(label).indexOf(normalise(query));
  if (at < 0) return esc(label);
  return esc(label.slice(0, at)) + "<mark>" + esc(label.slice(at, at + query.length)) +
         "</mark>" + esc(label.slice(at + query.length));
}

const COMBO_LIMIT = 40;

function comboMatches(combo, query) {
  const q = normalise(query).trim();
  if (!q) return combo.options.slice(0, COMBO_LIMIT);
  // Rank by where the match lands: a name that starts with what was typed is
  // what the reader meant far more often than one that merely contains it.
  const starts = [], contains = [], byState = [];
  for (const option of combo.options) {
    const name = normalise(option.name);
    if (name.startsWith(q)) starts.push(option);
    else if (name.includes(q)) contains.push(option);
    else if (normalise(option.state || "").includes(q)) byState.push(option);
  }
  return starts.concat(contains, byState);
}

function renderComboList(combo, query) {
  const matches = comboMatches(combo, query);
  const shown = matches.slice(0, COMBO_LIMIT);
  combo.matches = shown;
  combo.active = shown.length ? 0 : -1;
  if (!shown.length) {
    combo.list.innerHTML = `<li class="empty">${esc(t("ui.noMatch"))}</li>`;
  } else {
    combo.list.innerHTML = shown.map((option, index) =>
      `<li role="option" data-index="${index}" class="${index === 0 ? "active" : ""}">` +
      markMatch(option.name, query.trim()) +
      (option.state ? ` <span class="state">${esc(option.state)}</span>` : "") +
      "</li>").join("") +
      (matches.length > shown.length
        ? `<li class="more">${esc(t("ui.more", { n: matches.length - shown.length }))}</li>`
        : "");
  }
  combo.list.hidden = false;
  combo.input.setAttribute("aria-expanded", "true");
}

function closeCombo(combo) {
  combo.list.hidden = true;
  combo.input.setAttribute("aria-expanded", "false");
}

function comboLabel(option) {
  return option.state ? `${option.name} — ${option.state}` : option.name;
}

function selectComboOption(combo, option, { silent } = {}) {
  if (!option) return;
  combo.selected = option;
  combo.hidden.value = option.id;
  combo.input.value = comboLabel(option);
  combo.input.classList.remove("unset");
  closeCombo(combo);
  if (!silent) combo.hidden.dispatchEvent(new Event("change", { bubbles: true }));
}

function setupCombo(name, options, initialId) {
  const combo = {
    name,
    options,
    hidden: $(name),
    input: $(name + "Search"),
    list: $(name + "List"),
    mic: $(name + "Mic"),
    matches: [],
    active: -1,
    selected: null,
  };
  combos[name] = combo;

  combo.input.oninput = () => renderComboList(combo, combo.input.value);
  combo.input.onfocus = () => {
    // Focusing to change a choice means replacing it, so the whole current
    // value is offered for overtyping rather than needing to be cleared.
    combo.input.select();
    renderComboList(combo, "");
  };
  combo.input.onkeydown = (event) => {
    if (combo.list.hidden && (event.key === "ArrowDown" || event.key === "Enter")) {
      renderComboList(combo, combo.input.value);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      if (!combo.matches.length) return;
      combo.active = (combo.active + step + combo.matches.length) % combo.matches.length;
      combo.list.querySelectorAll("li[data-index]").forEach((li) => {
        li.classList.toggle("active", +li.dataset.index === combo.active);
      });
      const active = combo.list.querySelector("li.active");
      if (active) active.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectComboOption(combo, combo.matches[combo.active]);
    } else if (event.key === "Escape") {
      closeCombo(combo);
      // Escape restores the committed choice; leaving half-typed text in a box
      // whose value is something else is how people ship the wrong lane.
      if (combo.selected) combo.input.value = comboLabel(combo.selected);
    }
  };
  combo.input.onblur = () => setTimeout(() => closeCombo(combo), 150);
  combo.list.onmousedown = (event) => {
    const item = event.target.closest("li[data-index]");
    if (!item) return;
    event.preventDefault();
    selectComboOption(combo, combo.matches[+item.dataset.index]);
  };

  setupVoice(combo);

  const initial = options.find((o) => o.id === initialId) || options[0];
  selectComboOption(combo, initial, { silent: true });
  return combo;
}

/* ------------------------------------------------------- voice input ----- */
// The Web Speech API is built into the browser, so this costs nothing and
// needs no key. Firefox does not implement it; there the button is hidden
// rather than left in place to disappoint.
const SpeechRecogniser = window.SpeechRecognition || window.webkitSpeechRecognition;

function setupVoice(combo) {
  if (!SpeechRecogniser) { combo.mic.hidden = true; return; }
  combo.mic.onclick = () => {
    if (combo.recogniser) { combo.recogniser.stop(); return; }
    const recogniser = new SpeechRecogniser();
    recogniser.lang = speechLocale();
    recogniser.interimResults = false;
    recogniser.maxAlternatives = 3;
    combo.recogniser = recogniser;
    combo.mic.classList.add("listening");
    combo.input.placeholder = t("ui.listening");

    recogniser.onresult = (event) => {
      // Try every alternative the recogniser offers, best first: place names
      // here are not in its vocabulary, so the top guess is often a common
      // word and the second is the town.
      const alternatives = [...event.results[0]].map((r) => r.transcript.trim());
      for (const spoken of alternatives) {
        const matches = comboMatches(combo, spoken);
        if (matches.length) {
          combo.input.value = spoken;
          renderComboList(combo, spoken);
          // Commit only on an unambiguous hit. Two candidates means the reader
          // should choose, not us.
          if (matches.length === 1 ||
              normalise(matches[0].name) === normalise(spoken)) {
            selectComboOption(combo, matches[0]);
          }
          return;
        }
      }
      combo.input.value = alternatives[0] || "";
      renderComboList(combo, combo.input.value);
    };
    recogniser.onerror = () => { combo.input.value = ""; };
    recogniser.onend = () => {
      combo.recogniser = null;
      combo.mic.classList.remove("listening");
      combo.input.placeholder = t("ui.search");
    };
    recogniser.start();
  };
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

function monthOptions() {
  return MONTHS.map(([code]) =>
    [code, code === "jul" ? `${t("month.jul")} ${t("month.peak")}` : t("month." + code)]);
}

function modeLabels() { return MODES.map((m) => [m, t("mode." + m)]); }

// The three month pickers are separate controls that must survive a language
// change without losing what the reader chose.
function fillMonths() {
  const options = monthOptions();
  for (const id of ["month", "riskMonth", "accessMonth"]) {
    const chosen = $(id).value || "jul";
    fillSelect($(id), options, chosen);
  }
}

/* --------------------------------------------------------- language ------ */
// Labels that interleave text with a live value cannot be a single data-i18n
// string. Each is rebuilt from its translation with the value spliced into the
// placeholder's position, which differs between languages - in Hindi the rupee
// figure lands in the middle of the phrase, in English near the front.
function composeLabel(lineId, key, placeholder, valueHtml) {
  const MARK = "\u0000";
  const [before, after = ""] = t(key, { [placeholder]: MARK }).split(MARK);
  $(lineId).innerHTML = esc(before) + valueHtml + esc(after);
}

function refreshComposedLabels() {
  composeLabel("votLine", "route.vot", "v",
               `<span id="votLabel">${esc($("vot").value)}</span>`);
  composeLabel("minLengthLine", "risk.minLen", "n",
               `<span id="minLengthL">${esc($("minLength").value)}</span>`);
  composeLabel("analysisHint", "analysis.hint", "tab",
               `<b>${esc(t("tab.route"))}</b>`);
}

function setupLanguagePicker() {
  const select = $("langSelect");
  select.innerHTML = LANGUAGES
    .map(([code, label]) => `<option value="${code}">${esc(label)}</option>`).join("");
  select.value = restoreLanguage();
  applyTranslations();
  refreshComposedLabels();

  select.onchange = () => {
    setLanguage(select.value);
    refreshComposedLabels();
    fillMonths();
    chipRow($("modeChips"), modeLabels(), state.modes, planRoute);
    chipRow($("riskModeChips"), modeLabels(), state.riskModes, drawRisk);
    for (const combo of Object.values(combos)) {
      combo.input.placeholder = t("ui.search");
    }
    // Results are generated HTML, so translating them means rendering them
    // again. Only the visible panel is redrawn - the others rebuild when the
    // reader opens them.
    const active = document.querySelector("nav button.active");
    if (active) active.onclick();
  };
}

async function boot() {
  // Junctions outnumber settlements two to one and cannot be chosen
  // meaningfully - "n4021632273" is not somewhere anyone ships from.
  const { places } = await api("/network/places?settlements_only=true");
  places.forEach((p) => (state.places[p.id] = p));
  // Not every settlement carries a state; a bare "Name —" reads as a bug.
  const options = places.map((p) => ({ id: p.id, name: p.name, state: p.state || "" }));

  setupCombo("origin", options, "KHM");
  setupCombo("destination", options, "GAU");
  fillMonths();

  chipRow($("modeChips"), modeLabels(), state.modes, planRoute);
  chipRow($("riskModeChips"), modeLabels(), state.riskModes, drawRisk);
  applyPriority();
  applyCargo();
  probeBasemaps();

  planRoute();
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
  const label = t("route.plan");
  button.disabled = true;
  button.textContent = t("route.planning");
  try {
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

function itineraryFeatures(itinerary, { chosen }) {
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
        chosen: chosen ? 1 : 0,
        // Alternatives are drawn in grey underneath so the reader can see the
        // options exist and how they differ, without competing with the plan
        // actually being recommended.
        colour: chosen ? (MODE_COLOUR[leg.mode] || "#9aa4ad") : "#9aa4ad",
        popup: `<strong>${esc(leg.from_name)} → ${esc(leg.to_name)}</strong><br>
                ${esc(leg.mode)} · ${esc(leg.route_ref)} · ${leg.distance_km} km<br>
                ${fmtH(leg.hours)} · ${fmtRs(leg.cost_per_tonne)}/t<br>
                risk <b style="color:${RISK_COLOUR[leg.risk.band]}">${esc(leg.risk.band)}</b>`,
      },
    });
  }
  return { features, coords };
}

function drawPlan(plan, highlightIndex = -1) {
  // Every option on the map at once: the alternatives in grey, the one being
  // recommended in mode colours on top. Seeing only the winner hides that a
  // choice was made at all.
  const itineraries = [plan.recommended, ...(plan.alternatives || [])];
  const chosenIndex = highlightIndex >= 0 ? highlightIndex + 1 : 0;

  let features = [];
  let coords = [];
  itineraries.forEach((itinerary, index) => {
    const built = itineraryFeatures(itinerary, { chosen: index === chosenIndex });
    features = features.concat(built.features);
    coords = coords.concat(built.coords);
  });
  // Chosen last so it paints over the greyed alternatives.
  features.sort((a, b) => a.properties.chosen - b.properties.chosen);

  setSource("route", features);
  fitTo(coords);
  legend(t("legend.route"),
    MODES.map((m) => [MODE_COLOUR[m], t({
      road: "legend.byRoad", rail: "legend.byRail",
      water: "legend.byWater", air: "legend.byAir",
    }[m])]).concat([["#9aa4ad", t("legend.other")]]),
    t("legend.routeNote"));
}

function renderRoute(plan) {
  const s = plan.recommended.summary;
  drawPlan(plan);

  const legs = plan.recommended.legs.map((leg) => {
    if (leg.type === "transfer") {
      return `<div class="leg transfer">
        <div class="where">${esc(t("res.transhipment", { place: leg.at_name }))}</div>
        <div class="meta">${esc(t("res.transhipmentCost", {
          from: t("mode." + leg.from_mode), to: t("mode." + leg.to_mode),
          hours: fmtH(leg.hours), cost: fmtRs(leg.cost_per_tonne) }))}</div>
      </div>`;
    }
    return `<div class="leg mode-${esc(leg.mode)}">
      <div class="where">${esc(leg.from_name)} → ${esc(leg.to_name)}</div>
      <div class="meta">${esc(t("mode." + leg.mode))} · ${esc(leg.route_ref)} · ${leg.distance_km} km · ${fmtH(leg.hours)}
        <span class="badge ${esc(leg.risk.band)}">${esc(t("band." + leg.risk.band))}</span></div>
    </div>`;
  }).join("");

  const alternatives = plan.alternatives.map((alt, index) => {
    const a = alt.summary;
    return `<div class="alt" data-alt="${index}">
      <strong>${esc(a.mode_chain.map((m) => t("mode." + m)).join(" → "))}</strong>
      <div class="meta">${fmtH(a.total_hours)} · ${fmtRs(a.cost_per_tonne)}/t · ${esc(t("res.changes", { n: a.transhipments }))}</div>
    </div>`;
  }).join("");

  $("routeResult").innerHTML = `
    <div class="stats">
      <div class="stat"><b>${fmtH(s.total_hours)}</b><span>${esc(t("res.doorToDoor"))}</span></div>
      <div class="stat"><b>${fmtRs(s.cost_per_tonne)}</b><span>${esc(t("res.freight"))}</span></div>
      <div class="stat"><b>${s.distance_km} km</b><span>${esc(t("res.distance"))}</span></div>
      <div class="stat"><b>${fmtH(s.expected_delay_hours)}</b><span>${esc(t("res.delay"))}</span></div>
    </div>
    <h2>${esc(t("res.journey"))}</h2>${legs}
    ${alternatives ? `<h2 style="margin-top:16px">${esc(t("res.others"))}</h2>
       <p class="hint">${esc(t("res.othersHint"))}</p>${alternatives}` : ""}
    <p class="note">${esc(t("res.delayNote", { month: t("month." + plan.month) }))}</p>`;

  document.querySelectorAll(".alt").forEach((element) => {
    element.onclick = () => {
      const index = +element.dataset.alt;
      drawPlan(plan, index);
      document.querySelectorAll(".alt").forEach((el) => el.classList.remove("chosen"));
      element.classList.add("chosen");
    };
  });
}

/* ----------------------------------------------------------- risk map ---- */

async function drawRisk() {
  setSource("route", []);
  const data = await api(`/network/segments?month=${$("riskMonth").value}`);
  const { segments, risk_model } = data;
  state.segments = segments;
  // Thousands of sub-kilometre link roads bury the corridors that matter.
  const minKm = +$("minLength").value;
  const hazard = $("hazard").value;
  const riskOf = (s) => (hazard === "probability" ? s.risk.probability : s.risk[hazard]);
  const shown = segments.filter(
    (s) => state.riskModes.has(s.mode) && s.distance_km >= minKm,
  );

  setSource("segments", shown.map((s) => ({
    type: "Feature",
    geometry: { type: "LineString", coordinates: s.geometry },
    properties: {
      colour: riskColour(bandOf(riskOf(s))),
      widthScale: RISK_WIDTH[bandOf(riskOf(s))] ?? 1,
      popup: `<strong>${esc(s.label)}</strong><br>
              ${esc(s.mode)} · ${esc(s.route_ref)} · ${esc(s.terrain)} · ${s.distance_km} km<br>
              <b>${esc(t("band." + bandOf(riskOf(s))))}</b> —
              about a ${(riskOf(s) * 100).toFixed(0)}% chance of disruption this month<br>
              <span style="opacity:.75">landslide ${(s.risk.landslide * 100).toFixed(0)}%
              · flood ${(s.risk.flood * 100).toFixed(0)}%</span>`,
    },
  })));
  setSource("places", []);
  legend(
    t("risk.legend"),
    Object.keys(RISK_COLOUR).map((band) => [RISK_COLOUR[band], t("band." + band)]),
    t("risk.legendNote"),
  );
  fitTo(shown.flatMap((s) => s.geometry));

  // Prefer segments a reader can place on a map: an unnamed junction pair is
  // a true finding but an unusable one.
  const worst = shown.filter((s) => s.named)
    .sort((a, b) => riskOf(b) - riskOf(a))
    .slice(0, 12).map((s) => `<tr>
      <td>${esc(s.label)}</td>
      <td>${esc(s.risk.dominant === "flood" ? t("risk.flood") : t("risk.landslide"))}</td>
      <td><span class="badge ${esc(bandOf(riskOf(s)))}">${(riskOf(s) * 100).toFixed(0)}%</span></td>
    </tr>`).join("");

  const history = data.landslide_history || { segments: 0, total: 1 };
  const covered = history.segments / Math.max(history.total, 1);
  const hidden = segments.length - shown.length;
  const historyNote = covered > 0.05
    ? "Estimated from terrain, past landslides on that stretch, how narrow the road is, and how much rain falls there."
    : "Estimated from terrain, road width and rainfall. We have no record of past "
      + "landslides on these roads, so the real risk on the worst stretches is "
      + "probably higher than shown.";

  $("riskResult").innerHTML = `
    <table><thead><tr><th>${esc(t("risk.thRoad"))}</th><th>${esc(t("risk.thHazard"))}</th>
    <th>${esc(t("risk.thRisk"))}</th></tr></thead>
    <tbody>${worst}</tbody></table>
    <p class="note">${esc(t("risk.showing", {
      shown: shown.length.toLocaleString("en-IN"), km: minKm,
      hidden: hidden.toLocaleString("en-IN") }))}</p>
    <p class="note">${esc(historyNote)}</p>
    ${floodNote(data.flood_model)}`;
}

/* ------------------------------------------------------ accessibility ---- */

function rampColour(value, worst, best) {
  // The same three validated colours as the risk map, interpolated. Red-amber-
  // green with four stops failed the colour-difference checks; three stops with
  // a clear lightness step do not.
  const t = Math.max(0, Math.min(1, (value - worst) / (best - worst || 1)));
  const stops = [[208, 59, 59], [237, 161, 0], [27, 175, 122]];
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
  const values = data.places
    .filter((p) => p.is_settlement)
    .map((p) => p[metric])
    .filter((v) => v != null);
  const lo = Math.min(...values), hi = Math.max(...values);

  setSource("segments", []);
  // Only settlements. A junction is a graph node with an OSM id for a name, so
  // drawing them labels the map with "n10262284811".
  const settlements = data.places.filter((p) => p.is_settlement);
  setSource("places", settlements.map((p) => ({
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
    higherIsBetter ? t("access.legend") : t("access.metric" + (
      metric === "hours_to_market" ? "Market"
        : metric === "hours_to_coldstore" ? "Cold" : "Gateway")),
    [["rgb(27,175,122)", t("access.legendGood")],
     ["rgb(237,161,0)", t("access.legendMid")],
     ["rgb(208,59,59)", t("access.legendBad")]],
    higherIsBetter
      ? "Blends time to a market, cold store and the national gateway, plus how much worse the monsoon makes it."
      : "Real driving time over the road network, not distance on a map.",
  );

  const rows = data.underserved.map((p) => `<tr class="clickable" data-lon="${p.lon}" data-lat="${p.lat}">
      <td>${esc(p.name)}</td><td>${esc(p.state)}</td>
      <td>${p.accessibility_score}</td><td>${fmtH(p.hours_to_market)}</td>
    </tr>`).join("");

  $("accessResult").innerHTML = `
    <h2 style="margin-top:16px">${esc(t("access.worst"))}</h2>
    <p class="hint">${esc(t("access.worstHint"))}</p>
    <table><thead><tr><th>${esc(t("access.thPlace"))}</th><th>${esc(t("access.thState"))}</th>
    <th>${esc(t("access.thScore"))}</th><th>${esc(t("access.thMarket"))}</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="note">${esc(t("access.ranking", {
      n: data.settlements.toLocaleString("en-IN"),
      orphans: (data.unreachable || 0).toLocaleString("en-IN") }))}</p>`;

  document.querySelectorAll("#accessResult tr.clickable").forEach((row) => {
    row.onclick = () => map.flyTo({ center: [+row.dataset.lon, +row.dataset.lat], zoom: 8.5 });
  });
}

/* ------------------------------------------------------------ analysis --- */

async function runAnalysis() {
  const button = $("analysisRun");
  const label = t("analysis.run");
  button.disabled = true;
  button.textContent = t("analysis.running");
  try {
    const data = await api(`/routing/compare?month=${$("month").value}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: $("origin").value,
        destination: $("destination").value,
        value_of_time: +$("vot").value,
      }),
    });
    renderAnalysis(data);
  } catch (error) {
    $("analysisResult").innerHTML = `<div class="error">${esc(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function renderAnalysis(data) {
  const usable = data.options.filter((o) => o.available);
  const missing = data.options.filter((o) => !o.available);
  const best = data.best;
  const byKey = Object.fromEntries(usable.map((o) => [o.key, o]));

  const rows = usable.map((o) => {
    const tags = [];
    if (o.key === best.overall) tags.push("Recommended");
    if (o.key === best.cheapest) tags.push("Cheapest");
    if (o.key === best.fastest) tags.push("Fastest");
    if (o.key === best.most_reliable) tags.push("Most reliable");
    return `<tr class="${o.key === best.overall ? "winner" : ""}">
      <td>${esc(o.label)}${tags.length
        ? `<br><span class="badge best">${esc(tags.join(" · "))}</span>` : ""}</td>
      <td>${esc(o.mode_chain.join(" → "))}</td>
      <td>${fmtH(o.total_hours)}</td>
      <td>${fmtRs(o.cost_per_tonne)}</td>
      <td>${fmtH(o.expected_delay_hours)}</td>
    </tr>`;
  }).join("");

  // The prose is the point of this view: a table of seven rows still leaves the
  // reader to work out what the trade-off actually is.
  const rec = byKey[best.overall];
  const cheap = byKey[best.cheapest];
  const quick = byKey[best.fastest];
  const timeSaved = rec.total_hours - quick.total_hours;
  const extraCost = quick.cost_per_tonne - rec.cost_per_tonne;
  const savings = rec.cost_per_tonne - cheap.cost_per_tonne;
  const slower = cheap.total_hours - rec.total_hours;

  const paragraphs = [];
  paragraphs.push(
    `Moving freight from <b>${esc(data.origin.name)}</b> to
     <b>${esc(data.destination.name)}</b> in <b>${esc(MONTH_NAME[data.month] || data.month)}</b>,
     there are <b>${data.distinct_plans}</b> genuinely different ways to do it.
     The recommendation is <b>${esc(rec.mode_chain.join(" → "))}</b>:
     ${fmtH(rec.total_hours)} door to door at ${fmtRs(rec.cost_per_tonne)} per tonne.`);

  if (quick.key !== best.overall && timeSaved > 0.5) {
    paragraphs.push(
      `Flying or otherwise rushing it saves <b>${fmtH(timeSaved)}</b> but costs
       <b>${fmtRs(extraCost)}</b> more per tonne — worth it only if the cargo is
       losing more than that in the time saved.`);
  }
  if (cheap.key !== best.overall && savings > 1) {
    paragraphs.push(
      `The cheapest option saves <b>${fmtRs(savings)}</b> per tonne but takes
       <b>${fmtH(slower)}</b> longer.`);
  }
  if (rec.transhipments > 0) {
    paragraphs.push(
      `The recommended plan changes mode <b>${rec.transhipments}</b>
       time${rec.transhipments > 1 ? "s" : ""}. Each change means unloading and
       reloading, which is where multimodal plans usually lose the time they
       gain on the line haul.`);
  }
  paragraphs.push(
    `Across all options the spread is <b>${fmtRs(data.spread.cost_per_tonne)}</b>
     per tonne and <b>${fmtH(data.spread.hours)}</b> — the cost of choosing badly
     on this lane.`);

  $("analysisResult").innerHTML = `
    <div class="verdict">${paragraphs.join("</p><p style='margin:10px 0 0'>")}</div>
    <h2>${esc(t("analysis.every"))}</h2>
    <div style="overflow-x:auto">
      <table class="compare"><thead><tr>
        <th>${esc(t("analysis.thOption"))}</th><th>${esc(t("analysis.thRoute"))}</th>
        <th>${esc(t("analysis.thTime"))}</th><th>${esc(t("analysis.thCost"))}</th>
        <th>${esc(t("analysis.thDelay"))}</th>
      </tr></thead><tbody>${rows}</tbody></table>
    </div>
    ${missing.length ? `<h2 style="margin-top:16px">Not possible on this lane</h2>
      <p class="note">${missing.map((o) =>
        `<b>${esc(o.label)}</b> — ${esc(o.reason)}`).join("<br>")}</p>` : ""}
    <p class="note">"Delay" is the time this shipment can expect to lose to
       landslides and flooding in this month, already inside the door-to-door
       figure.</p>`;
}

/* --------------------------------------------------------------- wiring -- */

document.querySelectorAll("nav button").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === button));
    // Derived from the nav itself, so removing a tab cannot leave a stale name
    // here - listing them by hand threw on the deleted panel and broke every
    // tab, not just the one that had gone.
    document.querySelectorAll(".panel").forEach((panel) => {
      panel.hidden = panel.id !== "tab-" + button.dataset.tab;
    });
    if (button.dataset.tab === "risk") drawRisk();
    if (button.dataset.tab === "access") drawAccessibility();
    if (button.dataset.tab === "route") planRoute();
    if (button.dataset.tab === "analysis") runAnalysis();
  };
});

// Every control on this panel re-plans. Month, cargo and priority already did,
// while origin, destination and the mode chips did not - so changing where the
// consignment was going left the previous lane's numbers on screen, which is
// worse than showing nothing.
$("origin").onchange = planRoute;
$("destination").onchange = planRoute;
document.querySelectorAll("#basemapSwitch button").forEach((button) => {
  button.onclick = () => setBasemap(button.dataset.basemap);
});
$("priority").onchange = () => { applyPriority(); planRoute(); };
$("cargo").onchange = () => { applyCargo(); planRoute(); };
$("month").onchange = planRoute;
$("planBtn").onclick = planRoute;
$("analysisRun").onclick = runAnalysis;
function flashApplied(id) {
  const note = $(id);
  note.hidden = false;
  clearTimeout(note._timer);
  note._timer = setTimeout(() => (note.hidden = true), 4000);
}

// The map redraws on Apply, not on every control change: at 11,000 segments a
// redraw is visible work, and a map that lurches while you are still choosing
// gives no moment where you can see that your choice landed.
//
// The button holds a busy state for the whole redraw. Without it Apply looked
// inert for the two seconds the work actually takes, and there was no way -
// for a person or a test - to know whether a click had been taken.
async function applyWith(buttonId, noteId, draw) {
  const button = $(buttonId);
  const label = t(buttonId === "riskApply" ? "risk.apply" : "access.apply");
  button.disabled = true;
  button.textContent = t("risk.applying");
  $(noteId).hidden = true;
  try {
    await draw();
    flashApplied(noteId);
  } catch (error) {
    $("legend").innerHTML = "";
    console.error(error);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

$("riskApply").onclick = () => applyWith("riskApply", "riskApplied", drawRisk);
$("accessApply").onclick = () =>
  applyWith("accessApply", "accessApplied", drawAccessibility);
$("minLength").oninput = (e) => ($("minLengthL").textContent = e.target.value);
$("riskMonth").onchange = () => applyWith("riskApply", "riskApplied", drawRisk);
// The rupee sign belongs to the label, not the value: prefixing it here too
// rendered "₹₹150" the moment anyone dragged the slider.
$("vot").oninput = (e) => ($("votLabel").textContent = e.target.value);
for (const key of ["Cost", "Time", "Risk"]) {
  $("w" + key).oninput = (e) => ($("w" + key + "L").textContent = (+e.target.value).toFixed(2));
}

function fatal(message) {
  const banner = document.createElement("div");
  banner.className = "error";
  banner.style.margin = "12px 16px";
  banner.innerHTML =
    `<strong>The dashboard could not start.</strong><br>${esc(message)}<br><br>` +
    `Check the terminal running <code>run.sh</code> / <code>run.ps1</code>, then ` +
    `reload with <b>Ctrl+Shift+R</b>.`;
  $("sidebar").insertBefore(banner, $("sidebar").children[2]);
}

setupLanguagePicker();

boot().catch((error) => {
  // Empty dropdowns with no explanation is the worst possible failure mode:
  // it looks like the app, only broken. Say what happened, at the top.
  fatal(error.message);
  console.error(error);
});
