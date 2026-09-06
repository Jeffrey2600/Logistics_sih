#!/usr/bin/env python3
"""Fetch per-place monthly rainfall climatology from NASA POWER.

Replaces the single region-wide seasonal rain index in backend/app/config.py
with a real, spatially varying one. This matters more in the NER than almost
anywhere: Mawsynram and Cherrapunji are the wettest inhabited places on earth,
while the Imphal valley in the Manipur rain shadow gets a fraction of that. One
index for the whole region prices a Shillong hill road and an Imphal valley
road as if the same weather fell on both.

Source: NASA POWER climatology API. Free, no key, global 0.5 x 0.625 degree
grid, MERRA-2 reanalysis corrected against gauge data.

Output
------
data/processed/place_rainfall.csv   place_id, jan..dec (mm/day), rain_index

`rain_index` normalises each place-month against the wettest place-month in the
region, so it drops into the risk model in place of the hardcoded table.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROCESSED_DIR, ensure_dirs, fetch_json, load_seed_places  # noqa: E402

POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

# Be a good citizen of a free public API.
REQUEST_DELAY_SECONDS = 0.6


def fetch_place(lat: float, lon: float) -> dict[str, float]:
    payload = fetch_json(POWER_URL, {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "format": "JSON",
    })
    try:
        monthly = payload["properties"]["parameter"]["PRECTOTCORR"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"Unexpected POWER response shape: {str(payload)[:300]}") from exc
    return {month: float(monthly[month.upper()]) for month in MONTHS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only fetch the first N places (for testing)")
    args = parser.parse_args()

    ensure_dirs()
    places = load_seed_places()
    ids = list(places)[: args.limit] if args.limit else list(places)

    rows = []
    for index, place_id in enumerate(ids, 1):
        place = places[place_id]
        print(f"[{index}/{len(ids)}] {place['name']}", flush=True)
        monthly = fetch_place(float(place["lat"]), float(place["lon"]))
        rows.append({"place_id": place_id, "name": place["name"], **monthly})
        time.sleep(REQUEST_DELAY_SECONDS)

    # Normalise against the wettest place-month observed, so the index stays on
    # the 0-1 scale the risk model expects.
    peak = max(row[month] for row in rows for month in MONTHS) or 1.0
    for row in rows:
        for month in MONTHS:
            row[f"index_{month}"] = round(row[month] / peak, 4)

    out_path = PROCESSED_DIR / "place_rainfall.csv"
    fields = ["place_id", "name"] + MONTHS + [f"index_{m}" for m in MONTHS]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {out_path} ({len(rows)} places; peak {peak:.1f} mm/day)")
    wettest = sorted(rows, key=lambda r: -max(r[m] for m in MONTHS))[:5]
    print("Wettest places by peak month:")
    for row in wettest:
        month = max(MONTHS, key=lambda m: row[m])
        print(f"  {row['name']:<16} {row[month]:>6.1f} mm/day in {month}")


if __name__ == "__main__":
    main()
