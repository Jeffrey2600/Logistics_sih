#!/usr/bin/env python3
"""Assemble the labelled dataset that ml/landslide/train.py fits.

Joins the seed network, the snapped COOLR landslide points and the NASA POWER
rainfall climatology into one row per (segment, month).

On the labels
-------------
There is no public feed of NER road closures. State PWD and NHIDCL publish
them as press notes and PDFs, irregularly, and no historical archive exists in
machine-readable form. So the label here is a *weak* one: a segment is marked
disrupted in a month if a landslide from the catalogue was recorded on it in
that calendar month, in any year.

That is a proxy, and it is biased in known directions:

* COOLR is media-reported, so it over-samples slides near towns and along
  roads journalists drive, and under-samples remote stretches. A quiet segment
  may be genuinely safe or merely unwatched.
* A recorded slide is not the same event as a road closure. Small slips get
  cleared within hours and never close anything; the label cannot tell them
  apart.
* Reporting density rose sharply after about 2010 as smartphones spread, so
  raw event counts trend upward for reasons that have nothing to do with slope
  stability.

The right fix is a ground-truth channel: operator and driver reports of actual
closures, collected through the platform itself and fed back as labels. Until
that exists, treat the learned model as a refinement of the analytic prior
rather than as independent evidence, and quote the analytic model's reasoning
when explaining a score to a user.

Usage
-----
    python data/ingest/fetch_landslides.py
    python data/ingest/fetch_rainfall.py
    python data/ingest/build_training_set.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    PROCESSED_DIR, RAW_DIR, ensure_dirs, load_seed_edges, load_seed_places,
    point_to_segment_km,
)

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
SNAP_RADIUS_KM = 8.0
ACCURACY_KM = {"exact": 0.1, "1km": 1.0, "5km": 5.0, "10km": 10.0,
               "25km": 25.0, "50km": 50.0, "unknown": 999.0}


def month_of(event_date) -> str | None:
    """COOLR dates arrive as epoch milliseconds or ISO strings."""
    if event_date in (None, ""):
        return None
    try:
        if isinstance(event_date, (int, float)):
            return MONTHS[datetime.utcfromtimestamp(event_date / 1000).month - 1]
        return MONTHS[datetime.fromisoformat(str(event_date)[:19]).month - 1]
    except (ValueError, OSError, OverflowError):
        return None


def events_by_segment_month(points: list[dict], places: dict, edges: list[dict]) -> dict:
    usable = [
        p for p in points
        if ACCURACY_KM.get(str(p.get("location_accuracy", "unknown")).lower(), 999.0) <= 10.0
        and p.get("latitude") is not None and p.get("longitude") is not None
        and month_of(p.get("event_date"))
    ]
    print(f"{len(usable)} of {len(points)} catalogue points are usable (precise and dated)")

    hits: dict[tuple[str, str], int] = defaultdict(int)
    for edge in edges:
        if edge["mode"] not in ("road", "rail"):
            continue
        a, b = places[edge["u"]], places[edge["v"]]
        segment_id = f"{edge['u']}-{edge['v']}-{edge['mode']}"
        for point in usable:
            distance = point_to_segment_km(
                float(point["latitude"]), float(point["longitude"]),
                float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]),
            )
            if distance <= SNAP_RADIUS_KM:
                hits[(segment_id, month_of(point["event_date"]))] += 1
    return hits


def main() -> None:
    ensure_dirs()
    raw_path = RAW_DIR / "landslides_ner.json"
    if not raw_path.exists():
        raise SystemExit(
            f"{raw_path} not found. Run data/ingest/fetch_landslides.py first."
        )

    points = json.loads(raw_path.read_text())
    places, edges = load_seed_places(), load_seed_edges()
    hits = events_by_segment_month(points, places, edges)

    totals: dict[str, int] = defaultdict(int)
    for (segment_id, _month), count in hits.items():
        totals[segment_id] += count

    rows = []
    for edge in edges:
        if edge["mode"] not in ("road", "rail"):
            continue
        segment_id = f"{edge['u']}-{edge['v']}-{edge['mode']}"
        for month in MONTHS:
            rows.append({
                "segment_id": segment_id,
                "u": edge["u"],
                "v": edge["v"],
                "month": month,
                "terrain": edge["terrain"],
                "mode": edge["mode"],
                "distance_km": edge["distance_km"],
                "lanes": edge["lanes"],
                "monsoon_exposure": edge["monsoon_exposure"],
                "landslide_events": totals.get(segment_id, 0),
                "disrupted": int(hits.get((segment_id, month), 0) > 0),
            })

    out_path = PROCESSED_DIR / "disruption_training.csv"
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    positives = sum(r["disrupted"] for r in rows)
    print(f"Wrote {out_path}: {len(rows)} rows, {positives} labelled disrupted "
          f"({positives / len(rows):.1%})")
    if positives < 30:
        print("\nToo few positive labels to fit responsibly. train.py will refuse "
              "this file, and it is right to: keep using the analytic model.")


if __name__ == "__main__":
    main()
