# -*- coding: utf-8 -*-
"""Assemble the dashboard into one self-contained HTML file.

The real app is a FastAPI process plus a static frontend. This bakes a snapshot
of the API's answers into the page so the whole thing runs in a browser with no
server at all - which is the only way to hand someone a link they can click.

It is a snapshot, and the page says so: combinations that were not baked report
that plainly rather than inventing an answer.
"""
import io, json, os, re, sys, glob

S = sys.argv[1]
FRONTEND = sys.argv[2]
OUT = sys.argv[3]
RAW = os.path.join(S, "raw")

r5 = lambda v: round(v, 5) if isinstance(v, float) else v
r3 = lambda v: round(v, 3) if isinstance(v, float) else v


def load(name):
    with io.open(os.path.join(RAW, name), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- places
places = load("places.json") if os.path.exists(os.path.join(RAW, "places.json")) else None
if places is None:
    with io.open(os.path.join(S, "places.json"), encoding="utf-8") as fh:
        places = json.load(fh)
places["places"] = [
    {k: (r5(p[k]) if k in ("lat", "lon") else p[k])
     for k in ("id", "name", "state", "lat", "lon", "kind") if k in p}
    for p in places["places"]
]

# ---------------------------------------------------------------- segments
# Only the corridors the map shows by default. The slider can go below 5 km in
# the real app; here it cannot, and the page says so.
MIN_KM = 5.0
segments = {}
for month in ("jul", "jan"):
    data = load(f"seg_{month}.json")
    kept = []
    for s in data["segments"]:
        if s["distance_km"] < MIN_KM:
            continue
        s["geometry"] = [[r5(x), r5(y)] for x, y in s["geometry"]]
        risk = s["risk"]
        s["risk"] = {
            "probability": r3(risk["probability"]),
            "landslide": r3(risk["landslide"]),
            "flood": r3(risk["flood"]),
            "band": risk["band"],
            "dominant": risk["dominant"],
            "expected_delay_hours": r3(risk.get("expected_delay_hours", 0)),
        }
        for drop in ("monsoon_exposure", "landslide_events", "lanes", "u", "v"):
            s.pop(drop, None)
        kept.append(s)
    data["segments"] = kept
    data["count"] = len(kept)
    segments[month] = data

# ---------------------------------------------------------------- access
access = {}
for month in ("jul", "jan"):
    data = load(f"access_{month}.json")
    trimmed = []
    for p in data["places"]:
        if not p.get("is_settlement"):
            continue
        trimmed.append({
            "id": p["id"], "name": p["name"], "state": p.get("state", ""),
            "lat": r5(p["lat"]), "lon": r5(p["lon"]),
            "is_settlement": True, "tier": p.get("tier", ""),
            "accessibility_score": p.get("accessibility_score"),
            "hours_to_market": r3(p.get("hours_to_market")) if p.get("hours_to_market") is not None else None,
            "hours_to_coldstore": r3(p.get("hours_to_coldstore")) if p.get("hours_to_coldstore") is not None else None,
            "hours_to_gateway": r3(p.get("hours_to_gateway")) if p.get("hours_to_gateway") is not None else None,
        })
    data["places"] = trimmed
    access[month] = data

# ---------------------------------------------------------------- routing
plans, compares = {}, {}
for path in sorted(glob.glob(os.path.join(RAW, "plan_*.json"))):
    origin, dest, month = re.match(r"plan_(\w+)_(\w+)_(\w+)\.json", os.path.basename(path)).groups()
    plans[f"{origin}|{dest}|{month}"] = load(os.path.basename(path))
for path in sorted(glob.glob(os.path.join(RAW, "cmp_*.json"))):
    origin, dest, month = re.match(r"cmp_(\w+)_(\w+)_(\w+)\.json", os.path.basename(path)).groups()
    compares[f"{origin}|{dest}|{month}"] = load(os.path.basename(path))

demo = {"places": places, "segments": segments, "access": access,
        "plans": plans, "compares": compares,
        "months": ["jul", "jan"], "minKm": MIN_KM}

# ---------------------------------------------------------------- assemble
def read(name):
    with io.open(os.path.join(FRONTEND, name), encoding="utf-8") as fh:
        return fh.read()

app_js = read("app.js")

# Swap the network layer for a lookup over the baked snapshot. Everything else
# in app.js - rendering, filtering, the map, the language switch - is untouched
# and runs exactly as it does against the live server.
old_api = '''async function api(path, options) {
  const response = await fetch(API + path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}'''
assert old_api in app_js, "api() not found - app.js changed shape"
new_api = '''async function api(path, options) {
  // Snapshot build: the same call signature, answered from baked data.
  const body = options && options.body ? JSON.parse(options.body) : {};
  const month = (path.match(/month=(\\w+)/) || [])[1] || body.month;
  await new Promise((r) => setTimeout(r, 120));   // keep the busy states visible

  if (path.startsWith("/network/places")) return DEMO.places;
  if (path.startsWith("/network/segments")) {
    const data = DEMO.segments[month];
    if (!data) throw new Error(DEMO_MSG.month);
    return data;
  }
  if (path.startsWith("/accessibility/index")) {
    const data = DEMO.access[month];
    if (!data) throw new Error(DEMO_MSG.month);
    return data;
  }
  const key = `${body.origin}|${body.destination}|${month}`;
  if (path.startsWith("/routing/plan")) {
    const plan = DEMO.plans[key];
    if (!plan) throw new Error(DEMO_MSG.lane);
    return plan;
  }
  if (path.startsWith("/routing/compare")) {
    const cmp = DEMO.compares[key];
    if (!cmp) throw new Error(DEMO_MSG.lane);
    return cmp;
  }
  throw new Error(DEMO_MSG.lane);
}'''
app_js = app_js.replace(old_api, new_api, 1)

# The month pickers must only offer months the snapshot actually holds.
old_months = '''function monthOptions() {
  return MONTHS.map(([code]) =>'''
new_months = '''function monthOptions() {
  return MONTHS.filter(([code]) => !window.DEMO || DEMO.months.includes(code)).map(([code]) =>'''
assert old_months in app_js
app_js = app_js.replace(old_months, new_months, 1)

html = read("index.html")
body = html.split("<body>", 1)[1].split("</body>", 1)[0]
# strip the script tags; everything is inlined below
body = re.sub(r'<script src="[^"]+"></script>', "", body)

banner = """
<div id="demoBanner">
  <strong>Live demo &mdash; a snapshot of the real system.</strong>
  Every number, road and village here was produced by the actual engine and
  frozen into this page, so it runs with no server. Two months (July and
  January) and eight lanes into Guwahati are baked in; other combinations say
  so rather than inventing an answer. Roads under 5&nbsp;km are left out to keep
  the page small. The satellite base map needs to fetch map tiles, which this
  page's security policy blocks &mdash; it works in the real application.
  <button type="button" id="demoBannerClose" aria-label="Dismiss">&times;</button>
</div>
"""

extra_css = """
#demoBanner { position: fixed; left: 0; right: 0; top: 0; z-index: 50;
  background: #10323c; color: #eaf1f4; font-size: 12px; line-height: 1.5;
  padding: 10px 44px 10px 16px; }
#demoBanner strong { color: #fff; }
#demoBanner button { position: absolute; right: 8px; top: 6px; background: none;
  border: 0; color: #cfe0e6; font-size: 20px; cursor: pointer; line-height: 1; }
body.has-banner { padding-top: 62px; }
body.has-banner #map { height: calc(100vh - 62px); }
@media (max-width: 900px) { body.has-banner #map { height: 55vh; } }
"""

# The Artifact host supplies <!doctype>, <html>, <head> and <body>, so the page
# is authored as content only - a wrapper of our own would be nested inside it.
page = f"""<title>NER Logistics &amp; Accessibility Intelligence</title>
<style>{read("vendor/maplibre-gl.css")}</style>
<style>{read("style.css")}</style>
<style>{extra_css}</style>
{banner}
{body}
<script>{read("vendor/maplibre-gl.js")}</script>
<script>
document.body.classList.add("has-banner");
const DEMO = {json.dumps(demo, separators=(",", ":"), ensure_ascii=False)};
const DEMO_MSG = {{
  lane: "This snapshot holds eight lanes into Guwahati for July and January. "
      + "Pick one of those, or run the full application for any combination.",
  month: "This snapshot holds July and January only."
}};
document.getElementById("demoBannerClose").onclick = () => {{
  document.getElementById("demoBanner").remove();
  document.body.classList.remove("has-banner");
  if (window.map) map.resize();
}};
</script>
<script>{read("i18n.js")}</script>
<script>{app_js}</script>
"""

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write(page)
print("wrote", OUT, "%.1f MB" % (os.path.getsize(OUT) / 1e6))
print("segments jul/jan:", len(segments["jul"]["segments"]), len(segments["jan"]["segments"]))
print("settlements:", len(access["jul"]["places"]), "| plans:", len(plans), "| compares:", len(compares))
