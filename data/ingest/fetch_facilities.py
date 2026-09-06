#!/usr/bin/env python3
"""Fetch markets from OSM and flag them onto the network.

The accessibility index measures travel time to the nearest market. With the
settlement layer in place it scores 5,609 settlements against the 35 markets
carried by the hand-built seed - roughly one market per 160 settlements. Every
"hours to market" figure is therefore overstated: the villages became real, the
facilities they are measured against did not.

`amenity=marketplace` is the OSM tag for a mandi or bazaar. Markets are mapped
both as nodes and as areas, so ways and relations are fetched too and reduced to
their centre.

On cold storage: OSM has no usable tag coverage for it in the NER, so cold
stores remain the 15 curated seed entries. That is a real limit, recorded in
the README rather than papered over with a proxy tag that would look like data.

Outputs
-------
data/raw/osm_markets.json          raw Overpass response, cached
data/processed/facility_flags.csv  node_id, has_market, source

Usage
-----
    python data/ingest/fetch_facilities.py
    python data/ingest/fetch_facilities.py --from-file data/raw/osm_markets.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROCESSED_DIR, RAW_DIR, ensure_dirs  # noqa: E402
from fetch_osm import NER_REGIONS, region_bbox, run_query, tiles, write_csv  # noqa: E402
from places import _grid_index, nearest_node  # noqa: E402

NETWORK_NODES = PROCESSED_DIR / "osm_nodes.csv"
SETTLEMENT_NODES = PROCESSED_DIR / "settlement_nodes.csv"

# A market further than this from the network cannot be reached by the model.
MAX_ATTACH_KM = 10.0


def build_query(relation_id: int, bbox=None, timeout: int = 300) -> str:
    clip = ""
    if bbox:
        south, west, north, east = bbox
        clip = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"rel({relation_id}); map_to_area->.a;\n"
        f"(\n"
        f'  node(area.a)["amenity"="marketplace"]{clip};\n'
        f'  way(area.a)["amenity"="marketplace"]{clip};\n'
        f'  relation(area.a)["amenity"="marketplace"]{clip};\n'
        f");\n"
        f"out center;"
    )


def element_point(element: dict) -> tuple[float, float] | None:
    """Nodes carry lat/lon; ways and relations carry a `center` from `out center`."""
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    centre = element.get("center")
    if centre:
        return float(centre["lat"]), float(centre["lon"])
    return None


def download(regions) -> dict:
    print(f"Fetching markets for {len(regions)} regions…")
    merged: dict[tuple[str, int], dict] = {}

    for index, (name, relation_id, bbox) in enumerate(regions, 1):
        label = f"  [{index}/{len(regions)}] {name}"
        try:
            payload = run_query(build_query(relation_id, bbox))
            elements = [e for e in payload.get("elements", []) if element_point(e)]
            if not elements:
                raise SystemExit(f"{name} returned no markets")
        except SystemExit as exc:
            # A region genuinely may have no mapped marketplace, so unlike the
            # road and settlement walks an empty result is not fatal - but it is
            # worth one tiled retry before believing it.
            area = bbox or region_bbox(relation_id)
            grid = tiles(area)
            print(f"{label}: {exc}; retrying as {len(grid)} tiles", flush=True)
            seen: dict[tuple[str, int], dict] = {}
            for sub in grid:
                sub_payload = run_query(build_query(relation_id, sub))
                for element in sub_payload.get("elements", []):
                    if element_point(element):
                        seen[(element["type"], element["id"])] = element
            elements = list(seen.values())
            if not elements:
                print(f"{label}: no markets mapped in OSM", flush=True)

        fresh = sum(1 for e in elements if (e["type"], e["id"]) not in merged)
        for element in elements:
            merged[(element["type"], element["id"])] = element
        print(f"{label}: {len(elements):>5} markets ({fresh:>5} new, "
              f"{len(merged):>6} total)", flush=True)

    return {"elements": list(merged.values())}


def load_network_nodes() -> dict[str, tuple[float, float]]:
    """Every node a market could attach to: road junctions and settlements."""
    nodes: dict[str, tuple[float, float]] = {}
    for path in (NETWORK_NODES, SETTLEMENT_NODES):
        if not path.exists():
            continue
        with path.open() as fh:
            for row in csv.DictReader(fh):
                nodes[row["id"]] = (float(row["lat"]), float(row["lon"]))
    if not nodes:
        raise SystemExit(
            f"{NETWORK_NODES} not found. Build the road network first:\n"
            "  python data/ingest/fetch_osm.py"
        )
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path)
    parser.add_argument("--only")
    parser.add_argument("--max-attach-km", type=float, default=MAX_ATTACH_KM)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    regions = NER_REGIONS
    if args.only:
        wanted = {n.strip().lower() for n in args.only.split(",")}
        regions = tuple(r for r in NER_REGIONS if r[0].lower() in wanted)

    if args.dry_run:
        for name, relation_id, bbox in regions:
            print(f"# {name}")
            print(build_query(relation_id, bbox))
            print("---")
        return

    ensure_dirs()
    raw_path = RAW_DIR / "osm_markets.json"

    if args.from_file:
        payload = json.loads(args.from_file.read_text())
        print(f"Loaded {args.from_file}")
    else:
        payload = download(regions)
        raw_path.write_text(json.dumps(payload))
        print(f"Wrote {raw_path} ({len(payload['elements'])} elements)")

    network = load_network_nodes()
    cell = 5.0 / 111.0
    buckets = _grid_index(network, cell)

    flagged: dict[str, str] = {}
    unattached = 0
    for element in payload["elements"]:
        point = element_point(element)
        if point is None:
            continue
        node_id, _km = nearest_node(point[0], point[1], network, buckets, cell,
                                    args.max_attach_km)
        if node_id is None:
            unattached += 1
            continue
        flagged.setdefault(node_id, f"osm:{element['type']}/{element['id']}")

    print(f"\n{len(payload['elements'])} markets in OSM")
    print(f"  attached to network nodes: {len(flagged)}")
    print(f"  beyond {args.max_attach_km:g} km of any node: {unattached}")

    write_csv(
        PROCESSED_DIR / "facility_flags.csv",
        [{"node_id": n, "has_market": 1, "has_coldstore": 0, "source": src}
         for n, src in sorted(flagged.items())],
        ["node_id", "has_market", "has_coldstore", "source"],
    )
    print(f"\nWrote facility_flags.csv to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
