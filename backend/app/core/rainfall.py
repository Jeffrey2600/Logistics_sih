"""Per-place monthly rainfall, from NASA POWER climatology.

One rain index for the whole NER is a bad approximation of a region that
contains both the wettest inhabited places on earth and the Imphal rain
shadow. When `data/processed/place_rainfall.csv` is present (built by
`data/ingest/fetch_rainfall.py`) the risk model uses a per-segment index
interpolated from its endpoints; otherwise it falls back to the region-wide
table in config.py, so the API works on a fresh clone with no network.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from ..config import PROCESSED_DIR, SEASON_RAIN_INDEX

RAINFALL_CSV = PROCESSED_DIR / "place_rainfall.csv"

# Written by data/ingest/fetch_osm.py: the same indices carried onto the OSM
# junctions, so expanding the network does not silently drop every new node
# back to the regional average.
OSM_RAINFALL_CSV = PROCESSED_DIR / "osm_rainfall.csv"


def _read(path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    try:
        with path.open() as fh:
            return {
                row["place_id"]: {
                    month: float(row[f"index_{month}"]) for month in SEASON_RAIN_INDEX
                }
                for row in csv.DictReader(fh)
            }
    except (KeyError, ValueError):
        # A malformed file must degrade to the regional table, not crash the API.
        return {}


@lru_cache(maxsize=1)
def place_rain_index() -> dict[str, dict[str, float]]:
    """{place_id: {month: 0-1 index}}, empty when no dataset is present.

    Measured seed places override interpolated OSM junctions where both exist.
    """
    return {**_read(OSM_RAINFALL_CSV), **_read(RAINFALL_CSV)}


def rain_index(edge: dict, month: str) -> float:
    """Rain index for a segment in a month, 0-1.

    A segment spans two places, so its exposure is the mean of the two ends.
    That is crude for a 300 km Himalayan road, but it is strictly better than
    one number for eight states, and it sharpens as the network is subdivided
    into real OSM ways.
    """
    key = month.lower()[:3]
    regional = SEASON_RAIN_INDEX.get(key, 0.5)

    table = place_rain_index()
    if not table:
        return regional

    values = [table[end][key] for end in (edge.get("u"), edge.get("v"))
              if end in table and key in table[end]]
    if not values:
        return regional
    return sum(values) / len(values)
