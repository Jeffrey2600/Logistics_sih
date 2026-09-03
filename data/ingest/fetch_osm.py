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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    NER_BBOX, PROCESSED_DIR, RAW_DIR, ensure_dirs, fetch, haversine_km,
    load_seed_places,
)
from osm import (  # noqa: E402
    DEFAULT_MERGE_RADIUS_KM, DEFAULT_SNAP_RADIUS_KM, HIGHWAY_CLASSES,
    build_network, degree_histogram, largest_component,
)

# Mirrors, tried in order. The main instance is the most rate-limited.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def build_query(classes: tuple[str, ...], timeout: int = 900) -> str:
    """Overpass QL for every highway of the given classes in the NER bbox.

    `out body geom` is required, not just `geom`: the node ids identify shared
    junctions between ways, and the geometry gives the traced length. Without
    the ids the network cannot be assembled at all.
    """
    bbox = f"{NER_BBOX['south']},{NER_BBOX['west']},{NER_BBOX['north']},{NER_BBOX['east']}"
    pattern = "|".join(classes)
    return (
        f"[out:json][timeout:{timeout}];\n"
        f'way["highway"~"^({pattern})$"]({bbox});\n'
        f"out body geom;"
    )


def download(query: str) -> dict:
    """POST the query to each mirror in turn."""
    body = ("data=" + query).encode()
    last: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"Querying {endpoint}…", flush=True)
        try:
            import urllib.request

            request = urllib.request.Request(
                endpoint, data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "User-Agent": "SIH26002-NER-Logistics/0.1"},
            )
            with urllib.request.urlopen(request, timeout=960) as response:
                return json.loads(response.read())
        except Exception as exc:  # noqa: BLE001 - any failure means try the next mirror
            print(f"  failed: {exc}", file=sys.stderr)
            last = exc
    raise SystemExit(
        f"Every Overpass mirror failed (last: {last}).\n"
        "Download the query result on an unrestricted network and re-run with "
        "--from-file. The query is printed above --dry-run."
    )


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
    parser.add_argument("--dry-run", action="store_true",
                        help="print the Overpass query and exit")
    args = parser.parse_args()

    classes = tuple(c.strip() for c in args.classes.split(",") if c.strip())
    query = build_query(classes)

    if args.dry_run:
        print(query)
        return

    ensure_dirs()
    raw_path = RAW_DIR / "osm_ner.json"

    if args.from_file:
        payload = json.loads(args.from_file.read_text())
        print(f"Loaded {args.from_file} ({len(payload.get('elements', []))} elements)")
    else:
        payload = download(query)
        raw_path.write_text(json.dumps(payload))
        print(f"Wrote {raw_path} ({len(payload.get('elements', []))} elements)")

    places = load_seed_places()
    network = build_network(payload, places, snap_radius_km=args.snap_km,
                            merge_radius_km=args.merge_km)

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
