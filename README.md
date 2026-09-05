# NER Logistics & Accessibility Intelligence

**SIH26002** · Ministry of Development of North Eastern Region (MDoNER)
*AI-Based Smart Logistics and Accessibility Intelligence Platform for the North Eastern Region*

Multimodal freight routing and spatial accessibility scoring for the eight North
Eastern states, with monsoon disruption risk priced into every segment.

---

## The problem, stated precisely

NER freight economics are broken by geography, not by inefficiency. Single-lane
national highways thread landslide-prone gorges; the entire region reaches the
rest of India through the 22 km Siliguri Corridor; rail gauge conversion is
incomplete; the Brahmaputra (NW-2) is navigable and barely used. For four months
a year the monsoon closes the corridors that the other eight months depend on.

Two distinct questions follow, and this platform answers both:

1. **Logistics.** Given a consignment, an origin, a destination and a month, what
   is the best combination of road, rail, waterway and air — and what does the
   monsoon do to that answer?
2. **Accessibility.** Which places are structurally cut off from markets, cold
   chain and the national gateway, how much worse does the monsoon make it, and
   where would the next facility do the most good?

The second is the half most solutions skip. It is also the half MDoNER invests
against.

## What it does

| Capability | Endpoint | Why it is not trivial |
|---|---|---|
| Optimal multimodal itinerary | `POST /routing/plan` | Minimises a blend of cost, time and expected disruption, not distance. Transhipment between modes is charged, not free. |
| Route alternatives | same, `alternatives` | Yen's k-shortest paths over the mode-layered graph, deduplicated. |
| Closure simulation | same, `blocked_edge_ids` | "Shut NH-10 and re-plan." Correctly reports that this *isolates* Sikkim, because it does. |
| Dry season vs monsoon | `POST /routing/seasonal` | The same lane in January and July, with the delta in hours and rupees. |
| Segment risk map | `GET /network/segments` | Per-segment disruption probability from terrain, landslide history, carriageway width and real per-place rainfall. |
| Accessibility index | `GET /accessibility/index` | Door-to-facility travel *hours* over the network, never straight-line distance, with a monsoon-reliability component. |
| Facility siting | `POST /accessibility/facility-impact` | Ranks candidate sites by population brought within reach, before anything is built. |

## Design decisions worth defending

**The graph is layered by mode.** A place served by road and water becomes two
graph nodes joined by a transfer edge carrying real handling cost and terminal
dwell. Routing on a flat graph gives away transhipments for free, which is
precisely what makes naive multimodal plans look better on paper than in a yard.

**Monthly risk and per-trip risk are different numbers.** The chance a segment
is disrupted *at some point in July* is the right input to a risk map and to
investment prioritisation. The chance *this consignment* meets that closure is
much lower. Conflating them prices every monsoon trip as if the closure were
certain, and every hill route becomes unusable rather than merely expensive.

**Rainfall is per-place, not per-region.** The NER contains both the wettest
inhabited places on earth and the Imphal rain shadow. Using one seasonal index
priced a Meghalaya hill road and a Manipur valley road as if the same weather
fell on both. With real NASA POWER climatology, Kohima–Imphal on NH-2 falls from
severe to high while Jowai–Silchar stays severe — which is what the geography
says should happen.

**The objective is generalised cost, not distance.** Weights over cost, time and
risk are per-request, and a value-of-time parameter converts delay into money.
Bulk cargo routes by rail; raise the value of time far enough and perishables
correctly choose to fly. Both behaviours are asserted in the test suite.

**The ML model is optional and the analytic model is the fallback.** A learned
classifier is loaded when one has been trained; otherwise a transparent
rule-based susceptibility score runs. Either way the *explanation* shown to the
user comes from the analytic terms, because "the gradient booster said 0.62" is
not an answer a district officer can act on.

## Running it

```bash
pip install -r requirements-dev.txt
uvicorn backend.app.main:app --reload
```

Then open <http://localhost:8000> for the dashboard, or
<http://localhost:8000/docs> for the API.

There are no external data dependencies at runtime: a seed network of 46 NER
places and 78 multimodal segments ships in `data/seed/`, and the rainfall
climatology is committed. It runs offline, on a fresh clone, immediately.

```bash
python -m pytest tests -q     # 144 tests
```

## Deployment

One FastAPI process serves both the API and the dashboard, so the whole product
is a single free-tier service. `render.yaml` and `Procfile` are included.

The dashboard has no build step and no runtime npm dependency — MapLibre is
vendored into `frontend/vendor/`. A demo that dies because the venue blocks a
CDN is not a demo. The basemap is an enhancement over a blank local style, so
every data layer still renders with no internet at all.

## Data

| Dataset | Source | Status |
|---|---|---|
| Seed network (46 places, 78 segments) | Hand-built from NH/NFR/NW-2 alignments | Committed |
| Monthly rainfall climatology | NASA POWER (free, no key) | **Fetched and committed** |
| Landslide occurrences | NASA COOLR / Global Landslide Catalog | Fetcher written, **not yet run** — host still blocked (see `docs/NETWORK_ACCESS.md`) |
| Road network at scale | OpenStreetMap via Overpass | Pipeline built and tested; download reachable via the Kumi mirror (see `docs/NETWORK_ACCESS.md`) |

```bash
python data/ingest/fetch_rainfall.py       # verified working
python data/ingest/fetch_landslides.py     # written, download unverified
python data/ingest/fetch_osm.py            # written, download unverified
python data/ingest/build_training_set.py
python ml/landslide/train.py
```

### OSM ingestion

OSM is a drawing, not a graph. One national highway is hundreds of `way`
objects, each with dozens of geometry nodes that exist only to trace a curve.
The pipeline in `data/ingest/osm.py` parses the ways, decides which nodes are
*interesting* (junctions, way endpoints, and the seed places), contracts every
chain between them into a single edge carrying the real traced length, and
infers the attributes the cost and risk models need.

Two decisions carry most of the weight:

- **Terrain from sinuosity.** Traced length over straight-line chord. A road
  that wanders 40% further than the chord is climbing something. This needs no
  elevation model, which matters because DEM APIs are rate-limited and often
  unreachable. It is a proxy: a straight road across a high plateau reads as
  plain.
- **Merge radius, not nearest node.** OSM routinely carries several
  coincident-but-distinct nodes where roads meet a town — separate
  carriageways, untagged duplicates, ways that simply do not share an endpoint.
  Anchoring only the nearest one leaves the rest as junctions metres away and
  fragments the graph at exactly the places the model cares most about, so
  everything within `--merge-km` collapses into the place.
- **Contract short stubs, never drop them.** OSM splits a highway at every
  change of tagging, so junctions are surrounded by links a few metres long.
  Filtering those out looks like tidying and is destructive: an edge is the only
  thing carrying connectivity, so deleting a 30 m link severs whatever it
  joined. On the first real extract that filter left a largest connected
  component of 20 nodes out of 768. Nodes within `--node-merge-m` are merged by
  union-find over a spatial grid instead, which took the same extract to
  426 of 432 nodes connected.

Queries are scoped to the nine administrative areas — the eight NE states plus
the Siliguri Corridor sliver of West Bengal — rather than a bounding box. The
NER envelope also contains all of Bangladesh, most of Bhutan and a slice of
Myanmar, and pulling those is not just slower: their roads would read to the
optimiser as usable freight corridors across borders that are closed to
through traffic.

Because Overpass mirrors rate-limit hard and are often unreachable, the
download is a thin isolated layer and everything else takes a saved response:

```bash
python data/ingest/fetch_osm.py --dry-run          # print the query
python data/ingest/fetch_osm.py --from-file data/raw/osm_ner.json
```

One teammate downloads once; everyone else builds the network offline from the
committed JSON.

**Using the built network** is opt-in, because the seed network is committed and
known-good while an OSM build is neither, and partial anchoring would silently
disconnect places rather than fail loudly:

```bash
NER_USE_OSM=1 uvicorn backend.app.main:app
```

The merged network takes roads from OSM and keeps rail, the NW-2 waterway and
air links from the seed. `/health` reports `network_source`, `connected`,
`components` and `orphaned_places`, so a fragmented build is visible before
anyone trusts a number from it.

## Honest limitations

These are real, and stating them is better than being asked about them.

1. **There is no live road-closure feed, at any price.** State PWD and NHIDCL
   publish closures as irregular press notes, with no machine-readable archive.
   The platform therefore *predicts* risk from rainfall and terrain rather than
   observing closures. Closing that loop needs a ground-truth channel — operator
   and driver reports collected through the platform itself — which is designed
   for but not built.
2. **The ML labels are weak.** With no closure archive, a "disruption" label is
   proxied by a catalogue landslide recorded on that segment in that month.
   COOLR is media-reported, so it over-samples slides near towns and
   under-samples remote stretches, and reporting density rose after ~2010 for
   reasons unrelated to slope stability. `train.py` refuses to fit on too few
   positives rather than produce a confident-looking artefact. Treat the learned
   model as a refinement of the analytic prior, not as independent evidence.
3. **Freight tariffs are modelled, not sourced.** Real rates are commercial.
   Every rate, speed and penalty lives in `backend/app/config.py` with a source
   note, so a surveyed number can replace an assumed one without touching the
   algorithms.
4. **The default network is coarse.** 46 towns, not 30,000 villages. The
   accessibility index is computed correctly over whatever network it is given,
   and the OSM pipeline that expands it is built and tested — but its download
   has never run, so no large network has actually been built and profiled.
   Expect the first real build to need tuning of the snap and merge radii, and
   expect accessibility to slow down: it runs a multi-source Dijkstra per
   facility class per month, which is fine over 46 nodes and will need caching
   over 50,000.
5. **Accessibility is scored at nodes, not over a population surface.** Proper
   spatial equity work would use a WorldPop raster and travel-time isochrones.

## Layout

```
backend/app/
  config.py            every assumed constant, with source notes
  core/
    network.py         seed loading, mode-layered graph construction
    costing.py         generalised cost, transfer penalties
    risk.py            analytic and learned disruption models
    rainfall.py        per-place NASA POWER index, with fallback
    features.py        feature extraction shared by training and inference
  services/
    routing.py         optimal itinerary, alternatives, seasonal comparison
    accessibility.py   accessibility index, facility-impact ranking
  api/routes/          HTTP layer
frontend/              dashboard: no build step, MapLibre vendored
data/seed/             the committed network
data/ingest/
  osm.py               OSM topology: parsing, contraction, classification
  fetch_osm.py         Overpass CLI, with an offline --from-file path
  fetch_rainfall.py    NASA POWER climatology
  fetch_landslides.py  NASA COOLR, snapped to segments
  build_training_set.py
ml/landslide/          model training
tests/                 144 tests
```
