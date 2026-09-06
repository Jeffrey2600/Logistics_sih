#!/usr/bin/env python3
"""Pull landslide occurrences for the NER and snap them onto network segments.

Source: NASA's Cooperative Open Online Landslide Repository (COOLR), which
publishes the Global Landslide Catalog as an ArcGIS FeatureServer. It is free,
needs no key, and carries a date and a location accuracy for every point.

Output
------
data/raw/landslides_ner.json          the raw features, cached
data/processed/segment_landslides.csv segment_id, landslide_events, nearest_km

Caveats that belong in the report, not buried here:

* COOLR is media-reported. It systematically under-counts slides that blocked
  nothing newsworthy, and over-counts near towns with local press. Absence of
  points on a road is weak evidence that the road is safe.
* Location accuracy varies from "exact" to "within 50 km". Points coarser than
  the snapping radius are dropped rather than smeared across the network.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    NER_BBOX, PROCESSED_DIR, RAW_DIR, ensure_dirs, fetch_json,
    load_seed_edges, load_seed_places, point_to_segment_km,
)

COOLR_URL = (
    "https://maps.nccs.nasa.gov/arcgis/rest/services/global_landslide_catalog/"
    "global_landslide_catalog_point/MapServer/0/query"
)

# Accuracy classes coarser than this cannot be attributed to a specific road.
MAX_LOCATION_ACCURACY_KM = 10.0

# A slide within this distance of an alignment is treated as affecting it.
SNAP_RADIUS_KM = 8.0

ACCURACY_KM = {
    "exact": 0.1, "1km": 1.0, "5km": 5.0, "10km": 10.0,
    "25km": 25.0, "50km": 50.0, "unknown": 999.0,
}


def download() -> list[dict]:
    where = (
        f"latitude >= {NER_BBOX['south']} AND latitude <= {NER_BBOX['north']} AND "
        f"longitude >= {NER_BBOX['west']} AND longitude <= {NER_BBOX['east']}"
    )
    print("Querying NASA COOLR for NER landslide points…")
    payload = fetch_json(COOLR_URL, {
        "where": where,
        "outFields": "event_date,latitude,longitude,landslide_category,"
                     "landslide_trigger,location_accuracy,fatality_count",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": 5000,
    })
    if "features" not in payload:
        raise SystemExit(f"Unexpected COOLR response: {json.dumps(payload)[:400]}")
    return [f["attributes"] for f in payload["features"]]


def snap(points: list[dict], places: dict, edges: list[dict]) -> list[dict]:
    """Attribute each point to every segment it plausibly sits on."""
    usable = []
    for point in points:
        accuracy = ACCURACY_KM.get(str(point.get("location_accuracy", "unknown")).lower(), 999.0)
        if accuracy > MAX_LOCATION_ACCURACY_KM:
            continue
        if point.get("latitude") is None or point.get("longitude") is None:
            continue
        usable.append(point)

    print(f"{len(usable)} of {len(points)} points are precise enough to snap "
          f"(<= {MAX_LOCATION_ACCURACY_KM} km)")

    counts: dict[str, list[float]] = {}
    for edge in edges:
        if edge["mode"] not in ("road", "rail"):
            continue  # a landslide does not close a flight path
        a, b = places[edge["u"]], places[edge["v"]]
        segment_id = f"{edge['u']}-{edge['v']}-{edge['mode']}"
        for point in usable:
            distance = point_to_segment_km(
                float(point["latitude"]), float(point["longitude"]),
                float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]),
            )
            if distance <= SNAP_RADIUS_KM:
                counts.setdefault(segment_id, []).append(distance)

    return [
        {
            "segment_id": segment_id,
            "landslide_events": len(distances),
            "nearest_km": round(min(distances), 2),
        }
        for segment_id, distances in sorted(counts.items())
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", action="store_true",
                        help="reuse data/raw/landslides_ner.json instead of re-downloading")
    args = parser.parse_args()

    ensure_dirs()
    raw_path = RAW_DIR / "landslides_ner.json"

    if args.cache and raw_path.exists():
        points = json.loads(raw_path.read_text(encoding="utf-8"))
        print(f"Using cached {raw_path.name} ({len(points)} points)")
    else:
        points = download()
        raw_path.write_text(json.dumps(points, indent=1), encoding="utf-8")
        print(f"Wrote {raw_path} ({len(points)} points)")

    rows = snap(points, load_seed_places(), load_seed_edges())
    out_path = PROCESSED_DIR / "segment_landslides.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["segment_id", "landslide_events", "nearest_km"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {out_path}: {len(rows)} segments carry at least one recorded slide")
    for row in sorted(rows, key=lambda r: -r["landslide_events"])[:10]:
        print(f"  {row['segment_id']:<22} {row['landslide_events']:>4} events")


if __name__ == "__main__":
    main()
