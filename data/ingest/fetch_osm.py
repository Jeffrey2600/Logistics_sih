#!/usr/bin/env python3
"""Build a real road network for the NER from OpenStreetMap.

Replaces the 46-place hand-built seed network with the actual highway graph.
The accessibility index in particular gets much sharper: facility siting over
46 towns can only ever tell you about those towns.

Source: Overpass API (free, no key). Alternatively pass `--from-file` with a
previously saved Overpass JSON response, so one teammate downloads once and
everyone else builds the network offline. Overpass mirrors rate-limit hard and
are frequently unreachable from restricted networks, so prefer the cached file
for anything reproducible - including a demo.

Output
------
data/raw/osm_ner.json            the raw Overpass response, cached
data/processed/osm_nodes.csv     junctions and anchored seed places
data/processed/osm_edges.csv     contracted road segments
data/processed/osm_rainfall.csv  rainfall indices extended to the new nodes

Usage
-----
    python data/ingest/fetch_osm.py --classes motorway,trunk,primary
    python data/ingest/fetch_osm.py --from-file data/raw/osm_ner.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    NER_BBOX, PROCESSED_DIR, RAW_DIR, ensure_dirs, fetch, haversine_km,
    load_seed_places,
)
from osm import (  # noqa: E402
    DEFAULT_MERGE_RADIUS_KM, DEFAULT_NODE_MERGE_METRES, DEFAULT_SNAP_RADIUS_KM,
    HIGHWAY_CLASSES, build_network, degree_histogram, largest_component,
)

# Mirrors, tried in order. Kumi is first because it is the most tolerant of
# large extracts; the main instance rate-limits hardest.
OVERPASS_ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# 504s from an Overpass mirror are routine and transient - the same query
# succeeds seconds later - so each mirror is retried before moving on.
ATTEMPTS_PER_MIRROR = 3

# Query by administrative area, not by bounding box. The NER envelope also
# contains all of Bangladesh, most of Bhutan and a slice of Myanmar; pulling
# those is both far slower and wrong, because their roads would appear to the
# optimiser as usable freight corridors when the borders are closed to through
# traffic. OSM relation ids for the eight NE states, plus the sliver of West
# Bengal that carries the Siliguri Corridor - the region's only land link to
# the rest of India, so it has to be in the model.
NER_REGIONS = (
    ("Arunachal Pradesh", 2027346, None),
    ("Assam", 2025886, None),
    ("Manipur", 2027869, None),
    ("Meghalaya", 2027521, None),
    ("Mizoram", 2029046, None),
    ("Nagaland", 2027973, None),
    ("Sikkim", 1791324, None),
    ("Tripura", 2026458, None),
    # West Bengal is huge and mostly irrelevant here, so it is clipped to the
    # corridor. The eastern edge must reach the Assam border near Dhubri: NH-27
    # leaves Siliguri and runs east through Jalpaiguri and Cooch Behar, and
    # clipping at 89.2 severed it, stranding Siliguri and Gangtok in their own
    # 723-node component - the corridor is the region's only land link to the
    # rest of India, so cutting it is the one edge that must never be lost.
    ("Siliguri Corridor (WB)", 1960177, (25.8, 87.9, 27.4, 90.0)),
)

# A state whose query keeps failing is retried as bbox tiles of this size,
# clipped to the state area. Assam and Arunachal are large enough to time out
# on a free mirror in one go.
FALLBACK_TILE_DEGREES = 1.5

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def build_query(classes: tuple[str, ...], relation_id: int,
                bbox: tuple[float, float, float, float] | None = None,
                timeout: int = 600) -> str:
    """Overpass QL for every highway of the given classes inside one state.

    `out body geom` is required, not just `geom`: the node ids identify shared
    junctions between ways, and the geometry gives the traced length. Without
    the ids the network cannot be assembled at all.
    """
    pattern = "|".join(classes)
    clip = ""
    if bbox:
        south, west, north, east = bbox
        clip = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"rel({relation_id}); map_to_area->.a;\n"
        f'way(area.a)["highway"~"^({pattern})$"]{clip};\n'
        f"out body geom;"
    )


def tiles(bbox: tuple[float, float, float, float],
          step: float = FALLBACK_TILE_DEGREES) -> list[tuple[float, float, float, float]]:
    """Split a bounding box into a grid, for retrying a state piecewise."""
    south0, west0, north0, east0 = bbox
    out = []
    south = south0
    while south < north0:
        north = min(south + step, north0)
        west = west0
        while west < east0:
            east = min(west + step, east0)
            out.append((round(south, 4), round(west, 4), round(north, 4), round(east, 4)))
            west = east
        south = north
    return out


def region_bbox(relation_id: int) -> tuple[float, float, float, float]:
    """Ask Overpass for a relation's bounding box.

    Only needed when a whole-area query has to be retried piecewise. Fetching it
    beats hardcoding nine bounding boxes that would silently rot as boundaries
    are re-drawn.
    """
    payload = run_query(f"[out:json][timeout:60];rel({relation_id});out bb;")
    for element in payload.get("elements", []):
        bounds = element.get("bounds")
        if bounds:
            return (bounds["minlat"], bounds["minlon"],
                    bounds["maxlat"], bounds["maxlon"])
    raise SystemExit(f"Could not read a bounding box for relation {relation_id}")


def run_query(query: str) -> dict:
    """POST one query, retrying each mirror before moving to the next.

    Overpass signals some failures inside an HTTP 200 by attaching a `remark`
    rather than an error status, so a payload carrying one is treated as a
    failure - otherwise a silently truncated extract becomes a silently
    truncated road network.
    """
    import urllib.request

    body = ("data=" + query).encode()
    last: Exception | None = None

    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, ATTEMPTS_PER_MIRROR + 1):
            try:
                request = urllib.request.Request(
                    endpoint, data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "User-Agent": "SIH26002-NER-Logistics/0.1"},
                )
                with urllib.request.urlopen(request, timeout=900) as response:
                    payload = json.loads(response.read())
                remark = payload.get("remark")
                if remark:
                    raise RuntimeError(f"Overpass remark: {remark}")
                return payload
            except Exception as exc:  # noqa: BLE001 - retry, then fail over
                last = exc
                if attempt < ATTEMPTS_PER_MIRROR:
                    delay = 5 * attempt
                    print(f"    {type(exc).__name__}; retry {attempt} in {delay}s",
                          file=sys.stderr, flush=True)
                    time.sleep(delay)
        print(f"    giving up on {endpoint}", file=sys.stderr, flush=True)

    raise SystemExit(
        f"Every Overpass mirror failed (last: {last}).\n"
        "Download the query results on an unrestricted network and re-run with "
        "--from-file. Print the queries with --dry-run."
    )


def download(classes: tuple[str, ...], regions=NER_REGIONS) -> dict:
    """Fetch each state in turn and merge, deduplicating by way id.

    Ways crossing a state boundary come back from both states, identically, so
    keying on the OSM way id is enough to merge them.
    """
    print(f"Fetching {len(regions)} regions…")
    merged: dict[int, dict] = {}

    for index, (name, relation_id, bbox) in enumerate(regions, 1):
        label = f"  [{index}/{len(regions)}] {name}"
        try:
            payload = run_query(build_query(classes, relation_id, bbox))
            ways = [e for e in payload.get("elements", []) if e.get("type") == "way"]
            if not ways:
                # An area query that resolves to nothing returns HTTP 200 with an
                # empty element list, so a state can vanish from the network in
                # total silence. Tripura did exactly that on the first full run.
                raise SystemExit(f"{name} returned no ways")
        except SystemExit as exc:
            # One state failing is not a reason to lose the rest: retry it
            # piecewise, still clipped to the same administrative area so the
            # tiles never leak across a national border.
            area = bbox or region_bbox(relation_id)
            grid = tiles(area)
            print(f"{label}: {exc}; retrying as {len(grid)} tiles", flush=True)
            seen: dict[int, dict] = {}
            for sub in grid:
                payload = run_query(build_query(classes, relation_id, sub))
                for element in payload.get("elements", []):
                    if element.get("type") == "way":
                        seen[element["id"]] = element
            ways = list(seen.values())
            if not ways:
                raise SystemExit(f"{name}: no ways even after tiling") from exc

        fresh = sum(1 for w in ways if w["id"] not in merged)
        for way in ways:
            merged[way["id"]] = way
        print(f"{label}: {len(ways):>6} ways ({fresh:>6} new, "
              f"{len(merged):>7} total)", flush=True)

    return {"elements": list(merged.values())}


def extend_rainfall(nodes: dict, places: dict) -> list[dict]:
    """Carry the seed rainfall climatology onto the new OSM junctions.

    Each junction inherits the indices of its nearest seed place. That is
    interpolation, not measurement, and it is coarse where seed places are
    sparse - but it keeps the per-place rainfall signal alive across the
    expanded network instead of silently collapsing back to one regional
    number for every new node.
    """
    source = PROCESSED_DIR / "place_rainfall.csv"
    if not source.exists():
        print("  no place_rainfall.csv; skipping rainfall extension")
        return []

    with source.open() as fh:
        seed_rain = {row["place_id"]: row for row in csv.DictReader(fh)}

    rows = []
    for node_id, node in nodes.items():
        if node_id in seed_rain:
            rows.append(seed_rain[node_id])
            continue
        nearest = min(
            (p for p in places.values() if p["id"] in seed_rain),
            key=lambda p: haversine_km(node["lat"], node["lon"],
                                       float(p["lat"]), float(p["lon"])),
            default=None,
        )
        if nearest is None:
            continue
        donor = dict(seed_rain[nearest["id"]])
        donor["place_id"] = node_id
        donor["name"] = f"{node['name']} (via {nearest['name']})"
        rows.append(donor)
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path,
                        help="use a saved Overpass JSON response instead of downloading")
    parser.add_argument("--classes", default=",".join(HIGHWAY_CLASSES),
                        help="comma-separated highway classes to include")
    parser.add_argument("--snap-km", type=float, default=DEFAULT_SNAP_RADIUS_KM,
                        help="how close an OSM node must be to a seed place to be it")
    parser.add_argument("--merge-km", type=float, default=DEFAULT_MERGE_RADIUS_KM,
                        help="collapse all OSM nodes within this distance of a seed place")
    parser.add_argument("--only", help="comma-separated region names to fetch")
    parser.add_argument("--node-merge-m", type=float, default=DEFAULT_NODE_MERGE_METRES,
                        help="collapse OSM nodes closer together than this (metres)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the Overpass queries and exit")
    args = parser.parse_args()

    classes = tuple(c.strip() for c in args.classes.split(",") if c.strip())

    regions = NER_REGIONS
    if args.only:
        wanted = {name.strip().lower() for name in args.only.split(",")}
        regions = tuple(r for r in NER_REGIONS if r[0].lower() in wanted)
        if not regions:
            raise SystemExit(
                "No region matched --only. Available: "
                + ", ".join(r[0] for r in NER_REGIONS)
            )

    if args.dry_run:
        for name, relation_id, bbox in regions:
            print(f"# {name}")
            print(build_query(classes, relation_id, bbox))
            print("---")
        return

    ensure_dirs()
    raw_path = RAW_DIR / "osm_ner.json"

    if args.from_file:
        payload = json.loads(args.from_file.read_text())
        print(f"Loaded {args.from_file} ({len(payload.get('elements', []))} elements)")
    else:
        payload = download(classes, regions)
        raw_path.write_text(json.dumps(payload))
        print(f"Wrote {raw_path} ({len(payload.get('elements', []))} elements)")

    places = load_seed_places()
    network = build_network(payload, places, snap_radius_km=args.snap_km,
                            merge_radius_km=args.merge_km,
                            node_merge_metres=args.node_merge_m)

    if not network.edges:
        raise SystemExit(
            "No usable ways in the payload. Check the highway classes and the "
            "bounding box, and that the response is an `out body geom` result."
        )

    anchored = sum(1 for node_id in network.nodes if node_id in places)
    component = largest_component(network)
    print(f"\nBuilt {len(network.nodes)} nodes and {len(network.edges)} edges")
    print(f"  seed places anchored:  {anchored}/{len(places)}")
    print(f"  largest component:     {len(component)}/{len(network.nodes)} nodes")
    print(f"  degree histogram:      {degree_histogram(network)}")

    total_km = sum(e["distance_km"] for e in network.edges)
    print(f"  total road length:     {total_km:,.0f} km")
    by_terrain: dict[str, int] = {}
    for edge in network.edges:
        by_terrain[edge["terrain"]] = by_terrain.get(edge["terrain"], 0) + 1
    print(f"  terrain split:         {by_terrain}")

    if anchored < len(places) * 0.8:
        print("\nWARNING: many seed places did not anchor onto the OSM graph. "
              "Raise --snap-km, or include more highway classes.")
    if len(component) < len(network.nodes) * 0.9:
        print("\nWARNING: the network is fragmented. Ferries and unmapped links "
              "leave real gaps in the NER, but check the class filter first.")

    write_csv(PROCESSED_DIR / "osm_nodes.csv", list(network.nodes.values()),
              ["id", "name", "state", "lat", "lon", "kind", "population",
               "has_market", "has_coldstore"])
    write_csv(PROCESSED_DIR / "osm_edges.csv", network.edges,
              ["u", "v", "mode", "distance_km", "terrain", "route_ref", "lanes",
               "highway", "bridge", "tunnel", "surface", "osm_way_id"])

    rain_rows = extend_rainfall(network.nodes, places)
    if rain_rows:
        write_csv(PROCESSED_DIR / "osm_rainfall.csv", rain_rows,
                  ["place_id", "name"] + MONTHS + [f"index_{m}" for m in MONTHS])
        print(f"  rainfall extended to:  {len(rain_rows)} nodes")

    print(f"\nWrote osm_nodes.csv and osm_edges.csv to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
