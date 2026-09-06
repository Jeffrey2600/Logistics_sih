"""Shared helpers for the ingestion scripts.

Every fetcher writes to data/raw/ and every builder writes to data/processed/,
so a failed download never corrupts a derived dataset.
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SEED_DIR = REPO_ROOT / "data" / "seed"

# The eight North Eastern states plus the Siliguri Corridor, which is not in
# the NER but is the only land link to the rest of India and so belongs in any
# honest model of the region's freight.
NER_BBOX = {"south": 21.9, "west": 87.9, "north": 29.6, "east": 97.5}

USER_AGENT = "SIH26002-NER-Logistics/0.1 (academic project; contact via repo)"


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def fetch(url: str, params: dict | None = None, retries: int = 4, timeout: int = 120) -> bytes:
    """GET with exponential backoff.

    Public research APIs rate-limit aggressively and time out under load, so a
    single failed request must not abort a long ingest run.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt == retries - 1:
                break
            delay = 2 ** (attempt + 1)
            print(f"  request failed ({exc}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    raise SystemExit(f"Could not fetch {url}: {last}")


def fetch_json(url: str, params: dict | None = None, **kwargs) -> dict:
    return json.loads(fetch(url, params, **kwargs))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def point_to_segment_km(
    lat: float, lon: float,
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    """Perpendicular distance from a point to a segment, in km.

    Uses a local equirectangular projection. Over the tens of kilometres that
    matter for snapping a landslide to a highway, the error is negligible and
    the arithmetic stays cheap enough to run over the whole catalogue.
    """
    scale = math.cos(math.radians(lat))
    px, py = lon * scale, lat
    ax, ay = lon1 * scale, lat1
    bx, by = lon2 * scale, lat2

    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return haversine_km(lat, lon, lat1, lon1)

    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return haversine_km(lat, lon, cy, cx / (scale or 1.0))


def load_seed_places() -> dict[str, dict]:
    import csv

    with (SEED_DIR / "nodes.csv").open(encoding="utf-8") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def load_seed_edges() -> list[dict]:
    import csv

    with (SEED_DIR / "edges.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
