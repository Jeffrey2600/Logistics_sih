# Network access log

Some data sources are unreachable from the office network and fine from the
personal laptop. This file tracks what is blocked where, so a source that
failed once is retried later rather than quietly dropped.

Update the status and date whenever a source is retried.

| Source | Host | Needed for | Status | Last checked |
|---|---|---|---|---|
| NASA POWER climatology | `power.larc.nasa.gov` | Per-place rainfall | **Working** — data fetched and committed | 2026-09-03 |
| Overpass (Kumi mirror) | `overpass.kumi.systems` | OSM road network | **Working** — slow, 504s are routine, retry | 2026-09-05 |
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

## Notes

- Overpass mirrors return HTTP 504 on perfectly valid queries under load. The
  ingester retries each mirror three times with backoff before failing over,
  and treats a `remark` field inside an HTTP 200 as a failure too — Overpass
  signals truncation that way, and a silently truncated extract would become a
  silently truncated road network.
- Any fetcher that cannot reach its source is expected to fail loudly rather
  than write a partial dataset. Derived data lives in `data/processed/` and is
  only written after a complete fetch.
