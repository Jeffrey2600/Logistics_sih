# Network access log

Some data sources are unreachable from the office network and fine from the
personal laptop. This file tracks what is blocked where, so a source that
failed once is retried later rather than quietly dropped.

Update the status and date whenever a source is retried.

| Source | Host | Needed for | Status | Last checked |
|---|---|---|---|---|
| NASA POWER climatology | `power.larc.nasa.gov` | Per-place rainfall | **Working** — data fetched and committed | 2026-09-03 |
| Overpass (Kumi mirror) | `overpass.kumi.systems` | OSM road network | **Working** — but rate-limits after sustained use; see below | 2026-09-05 |
| Overpass (main) | `overpass-api.de` | OSM road network | Blocked | 2026-09-05 |
| Geofabrik extracts | `download.geofabrik.de` | Bulk OSM `.osm.pbf` | Blocked | 2026-09-05 |
| NASA COOLR landslides | `maps.nccs.nasa.gov` | Landslide history, ML labels | Blocked | 2026-09-05 |
| MapLibre CDN | `cdn.jsdelivr.net` | Dashboard map library | Blocked — vendored into `frontend/vendor/`, no longer needed | 2026-09-03 |
| Basemap tiles | `tiles.openfreemap.org` | Dashboard basemap | Blocked — dashboard degrades to a blank style and still renders all data | 2026-09-03 |

## Still to retry

- **NASA COOLR** (`maps.nccs.nasa.gov`). Blocks landslide history on real
  segments and the ML training labels. Until it succeeds, `landslide_events`
  on OSM-derived segments is 0 and the risk model leans entirely on terrain,
  carriageway width and rainfall.
- **Geofabrik**. Not required — Overpass covers it — but a `.osm.pbf` extract
  would make rebuilds far faster than a 20-tile Overpass walk.

## Rate limiting

Free Overpass mirrors will start returning 504 on every request after a session
of sustained querying, and all three mirrors fail together because the limit is
per-client, not per-host. A full nine-region walk takes 10-15 minutes and is
enough to trigger it.

Two habits follow from that:

- Never repeat a full walk to fix part of one. `--merge-raw` fetches only the
  regions named with `--only` and merges them into the cached payload by way id,
  so a costly successful download stays useful.
- Keep `data/raw/osm_ner.json` safe. The ingester writes it only after every
  region returns, so a failed run leaves the last good payload in place - but a
  *successful* run replaces it, so back it up before experimenting.

Rebuilding the network from a cached payload needs no network at all:

    python data/ingest/fetch_osm.py --from-file data/raw/osm_ner.json

## Notes

- Overpass mirrors return HTTP 504 on perfectly valid queries under load. The
  ingester retries each mirror three times with backoff before failing over,
  and treats a `remark` field inside an HTTP 200 as a failure too — Overpass
  signals truncation that way, and a silently truncated extract would become a
  silently truncated road network.
- A mirror will also answer an area query with HTTP 200 and an empty element
  list, which is indistinguishable from a state that genuinely has no roads.
  This hit Tripura on one run and Arunachal Pradesh on the next, so it is
  general flakiness rather than a quirk of one boundary. An empty region is
  therefore treated as a failure and retried piecewise; without that, whichever
  state drew the short straw would vanish from the network in silence.
- Any fetcher that cannot reach its source is expected to fail loudly rather
  than write a partial dataset. Derived data lives in `data/processed/` and is
  only written after a complete fetch.
