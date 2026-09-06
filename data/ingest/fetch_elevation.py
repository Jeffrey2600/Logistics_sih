#!/usr/bin/env python3
"""Fetch ground elevation for every network node.

Flood risk in the NER is mostly a question of height. The Brahmaputra valley
floor sits at 40-90 m and floods every year; the hills either side are at 500 m
and never do. Without elevation the model cannot tell a road on the floodplain
from one on a ridge two kilometres away.

Source: Open-Meteo's elevation API - free, no key, no rate limit worth the name,
backed by the Copernicus 90 m DEM. Up to 100 coordinates per request.

Output
------
data/processed/node_elevation.csv   node_id, elevation_m

Usage
-----
    python data/ingest/fetch_elevation.py
    python data/ingest/fetch_elevation.py --limit 200      # smoke test
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROCESSED_DIR, ensure_dirs, fetch_json  # noqa: E402

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
NETWORK_NODES = PROCESSED_DIR / "osm_nodes.csv"
SETTLEMENT_NODES = PROCESSED_DIR / "settlement_nodes.csv"
OUT_PATH = PROCESSED_DIR / "node_elevation.csv"

# The API's documented maximum per call.
BATCH = 100
PAUSE_SECONDS = 0.25


def load_nodes() -> dict[str, tuple[float, float]]:
    nodes: dict[str, tuple[float, float]] = {}
    for path in (NETWORK_NODES, SETTLEMENT_NODES):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
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
    parser.add_argument("--limit", type=int, help="only fetch the first N nodes")
    args = parser.parse_args()

    ensure_dirs()
    nodes = load_nodes()
    ids = list(nodes)[: args.limit] if args.limit else list(nodes)
    print(f"Fetching elevation for {len(ids)} nodes in batches of {BATCH}…")

    rows: list[dict] = []
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        payload = fetch_json(ELEVATION_URL, {
            "latitude": ",".join(f"{nodes[i][0]:.5f}" for i in chunk),
            "longitude": ",".join(f"{nodes[i][1]:.5f}" for i in chunk),
        })
        elevations = payload.get("elevation")
        if not isinstance(elevations, list) or len(elevations) != len(chunk):
            raise SystemExit(
                f"Elevation API returned {len(elevations or [])} values for "
                f"{len(chunk)} coordinates; refusing to mis-align them."
            )
        rows.extend(
            {"node_id": node_id, "elevation_m": round(float(value), 1)}
            for node_id, value in zip(chunk, elevations)
        )
        done = start + len(chunk)
        if done % 1000 < BATCH:
            print(f"  {done}/{len(ids)}", flush=True)
        time.sleep(PAUSE_SECONDS)

    with OUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["node_id", "elevation_m"])
        writer.writeheader()
        writer.writerows(rows)

    heights = [r["elevation_m"] for r in rows]
    lowland = sum(1 for h in heights if h <= 100)
    print(f"\nWrote {OUT_PATH} ({len(rows)} nodes)")
    print(f"  range: {min(heights):.0f} m to {max(heights):.0f} m")
    print(f"  at or below 100 m (Brahmaputra/Barak floodplain): {lowland} "
          f"({lowland / len(rows):.0%})")


if __name__ == "__main__":
    main()
