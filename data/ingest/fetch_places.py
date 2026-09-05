#!/usr/bin/env python3
"""Fetch populated places from OSM and join them onto the road network.

The road network says how to get from A to B. It cannot say who is cut off,
because a junction is not a place anyone lives. Without this layer the
accessibility index ranks the 46 hand-built seed towns no matter how large the
road graph grows - which is the gap between "a routing demo" and the
accessibility intelligence the problem statement actually asks for.

Inputs
------
data/processed/osm_nodes.csv    the built road network (run fetch_osm.py first)

Outputs
-------
data/raw/osm_places.json              raw Overpass response, cached
data/processed/settlement_nodes.csv   settlements added as graph nodes
data/processed/settlement_edges.csv   last-mile connectors to the road network
data/processed/settlement_merges.csv  settlements that landed on an existing node

Usage
-----
    python data/ingest/fetch_places.py
    python data/ingest/fetch_places.py --from-file data/raw/osm_places.json
    python data/ingest/fetch_places.py --only Meghalaya
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROCESSED_DIR, RAW_DIR, ensure_dirs  # noqa: E402
from fetch_osm import (  # noqa: E402
    NER_REGIONS, region_bbox, run_query, tiles, write_csv,
)
from places import MAX_ATTACH_KM, PLACE_CLASSES, attach, parse_places  # noqa: E402

NETWORK_NODES = PROCESSED_DIR / "osm_nodes.csv"


def build_places_query(relation_id: int, bbox=None, timeout: int = 300) -> str:
    """Settlement nodes inside one state.

    Nodes only, and no geometry to fetch, so this is far lighter than the
    highway walk - a whole state comes back in seconds rather than minutes.
    """
    pattern = "|".join(PLACE_CLASSES)
    clip = ""
    if bbox:
        south, west, north, east = bbox
        clip = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"rel({relation_id}); map_to_area->.a;\n"
        f'node(area.a)["place"~"^({pattern})$"]{clip};\n'
        f"out body;"
    )


def download(regions) -> dict:
    """Fetch settlements per region, with the same tiled retry as the road walk.

    A mirror will answer an area query with HTTP 200 and an empty list, which is
    indistinguishable from a state with no settlements. Treating that as fatal
    lets one flaky region cost the other eight, so it falls back to tiles
    clipped to the same area instead.
    """
    print(f"Fetching settlements for {len(regions)} regions…")
    merged: dict[int, dict] = {}

    for index, (name, relation_id, bbox) in enumerate(regions, 1):
        label = f"  [{index}/{len(regions)}] {name}"
        try:
            payload = run_query(build_places_query(relation_id, bbox))
            nodes = [e for e in payload.get("elements", []) if e.get("type") == "node"]
            if not nodes:
                raise SystemExit(f"{name} returned no settlements")
        except SystemExit as exc:
            area = bbox or region_bbox(relation_id)
            grid = tiles(area)
            print(f"{label}: {exc}; retrying as {len(grid)} tiles", flush=True)
            seen: dict[int, dict] = {}
            for sub in grid:
                sub_payload = run_query(build_places_query(relation_id, sub))
                for element in sub_payload.get("elements", []):
                    if element.get("type") == "node":
                        seen[element["id"]] = element
            nodes = list(seen.values())
            if not nodes:
                raise SystemExit(f"{name}: no settlements even after tiling") from exc

        fresh = sum(1 for n in nodes if n["id"] not in merged)
        for element in nodes:
            merged[element["id"]] = element
        print(f"{label}: {len(nodes):>5} places ({fresh:>5} new, "
              f"{len(merged):>6} total)", flush=True)

    return {"elements": list(merged.values())}


def load_network_nodes() -> dict[str, tuple[float, float]]:
    if not NETWORK_NODES.exists():
        raise SystemExit(
            f"{NETWORK_NODES} not found. Build the road network first:\n"
            "  python data/ingest/fetch_osm.py"
        )
    with NETWORK_NODES.open() as fh:
        return {r["id"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path,
                        help="use a saved Overpass response instead of downloading")
    parser.add_argument("--only", help="comma-separated region names")
    parser.add_argument("--max-attach-km", type=float, default=MAX_ATTACH_KM,
                        help="furthest a settlement may sit from the road network")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    regions = NER_REGIONS
    if args.only:
        wanted = {n.strip().lower() for n in args.only.split(",")}
        regions = tuple(r for r in NER_REGIONS if r[0].lower() in wanted)
        if not regions:
            raise SystemExit("No region matched --only. Available: "
                             + ", ".join(r[0] for r in NER_REGIONS))

    if args.dry_run:
        for name, relation_id, bbox in regions:
            print(f"# {name}")
            print(build_places_query(relation_id, bbox))
            print("---")
        return

    ensure_dirs()
    raw_path = RAW_DIR / "osm_places.json"

    if args.from_file:
        payload = json.loads(args.from_file.read_text())
        print(f"Loaded {args.from_file}")
    else:
        payload = download(regions)
        raw_path.write_text(json.dumps(payload))
        print(f"Wrote {raw_path} ({len(payload['elements'])} elements)")

    settlements = parse_places(payload)
    network = load_network_nodes()
    print(f"\n{len(settlements)} named settlements; road network has {len(network)} nodes")

    nodes, edges, unattached, merges = attach(
        settlements, network, max_attach_km=args.max_attach_km
    )

    known = sum(1 for s in settlements if s.population_known)
    print(f"  attached as new nodes:  {len(nodes)}")
    print(f"  merged into a road node: {len(merges)}")
    print(f"  unattached (> {args.max_attach_km:g} km from any road): {len(unattached)}")
    print(f"  population tagged in OSM: {known}/{len(settlements)} "
          f"({known / max(len(settlements), 1):.0%})")

    if unattached:
        print("    e.g. " + ", ".join(s.name for s in unattached[:5]))

    write_csv(PROCESSED_DIR / "settlement_nodes.csv", nodes,
              ["id", "name", "state", "lat", "lon", "kind", "population",
               "population_known", "has_market", "has_coldstore"])
    write_csv(PROCESSED_DIR / "settlement_edges.csv", edges,
              ["u", "v", "mode", "distance_km", "terrain", "route_ref", "lanes",
               "highway", "bridge", "tunnel", "surface", "osm_way_id"])
    write_csv(
        PROCESSED_DIR / "settlement_merges.csv",
        [{"node_id": node_id, "name": s.name, "kind": s.place_type,
          "population": s.population, "population_known": int(s.population_known)}
         for node_id, s in sorted(merges.items())],
        ["node_id", "name", "kind", "population", "population_known"],
    )
    print(f"\nWrote settlement_nodes.csv, settlement_edges.csv and "
          f"settlement_merges.csv to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
