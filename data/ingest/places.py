"""Populated places: parsing OSM settlement nodes and attaching them to roads.

The road network answers "how do I get from A to B". It cannot answer "who is
cut off", because a road junction is not a place anyone lives. Until settlements
are in the graph, the accessibility index can only rank the 46 hand-built seed
towns however large the road network grows.

This module is pure: no network access, so the join logic that decides which
village hangs off which road is testable offline.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass

from common import haversine_km

# Settlement classes worth modelling. `isolated_dwelling` and `farm` are too
# fine-grained to be meaningful for freight and would swamp the graph.
PLACE_CLASSES = ("city", "town", "village", "hamlet", "suburb")

# A settlement further than this from any road is not attachable: either the
# road network is missing there, or the point is mis-tagged. Reported, not
# silently dropped.
MAX_ATTACH_KM = 20.0

# A settlement this close to an existing network node is that node - typically a
# seed place we already model, or a village mapped both as a node and a junction.
COINCIDENT_KM = 1.5

# Last-mile access roads are not straight. The connector length is the straight
# line to the nearest road node multiplied by this, in line with the circuity
# assumed elsewhere in the pipeline for hill roads.
ACCESS_CIRCUITY = 1.35


@dataclass(frozen=True)
class Settlement:
    osm_id: int
    name: str
    place_type: str
    lat: float
    lon: float
    population: int          # 0 when untagged
    population_known: bool

    @property
    def node_id(self) -> str:
        return f"s{self.osm_id}"


def parse_population(tags: dict) -> tuple[int, bool]:
    """Read an OSM population tag.

    Values in the wild include "12345", "12,345", "1 200", "approx 5000" and
    "1985" (a census year mis-entered). Anything that does not parse cleanly, or
    is implausible for a settlement, is treated as unknown rather than guessed:
    a fabricated population would flow straight into the facility-siting
    rankings and quietly decide where a cold store goes.
    """
    raw = tags.get("population")
    if raw is None:
        return 0, False
    digits = re.sub(r"[^\d]", "", str(raw))
    if not digits:
        return 0, False
    try:
        value = int(digits)
    except ValueError:
        return 0, False
    if not (1 <= value <= 30_000_000):
        return 0, False
    return value, True


def parse_places(payload: dict) -> list[Settlement]:
    """Read settlement nodes from an Overpass response."""
    out: list[Settlement] = []
    for element in payload.get("elements", []):
        if element.get("type") != "node":
            continue
        tags = element.get("tags") or {}
        place_type = tags.get("place", "")
        if place_type not in PLACE_CLASSES:
            continue
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue          # an unnamed settlement cannot be reported to anyone
        if element.get("lat") is None or element.get("lon") is None:
            continue
        population, known = parse_population(tags)
        out.append(
            Settlement(
                osm_id=element["id"],
                name=name,
                place_type=place_type,
                lat=float(element["lat"]),
                lon=float(element["lon"]),
                population=population,
                population_known=known,
            )
        )
    return out


def _grid_index(nodes: dict[str, tuple[float, float]], cell_deg: float):
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for node_id, (lat, lon) in nodes.items():
        buckets[(int(lat / cell_deg), int(lon / cell_deg))].append(node_id)
    return buckets


def nearest_node(
    lat: float,
    lon: float,
    nodes: dict[str, tuple[float, float]],
    buckets,
    cell_deg: float,
    max_km: float,
) -> tuple[str | None, float]:
    """Nearest network node within max_km, searched over a spatial grid.

    Widens the search ring until one is found or the ring exceeds max_km, so a
    settlement is never compared against every node in the region.
    """
    best_id, best_km = None, max_km
    rings = max(1, int(max_km / (cell_deg * 111.0)) + 1)
    row, col = int(lat / cell_deg), int(lon / cell_deg)

    for radius in range(rings + 1):
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                # Only the newly exposed ring, not the filled square again.
                if radius and max(abs(dr), abs(dc)) != radius:
                    continue
                for node_id in buckets.get((row + dr, col + dc), ()):
                    node_lat, node_lon = nodes[node_id]
                    distance = haversine_km(lat, lon, node_lat, node_lon)
                    if distance < best_km:
                        best_id, best_km = node_id, distance
        # A hit inside the current ring cannot be beaten by a ring further out.
        if best_id is not None and best_km <= radius * cell_deg * 111.0:
            break
    return best_id, best_km


def attach(
    settlements: list[Settlement],
    network_nodes: dict[str, tuple[float, float]],
    max_attach_km: float = MAX_ATTACH_KM,
    coincident_km: float = COINCIDENT_KM,
) -> tuple[list[dict], list[dict], list[Settlement]]:
    """Join settlements onto the road network.

    Returns (nodes, connector_edges, unattached, merged_into), where
    `merged_into` maps an existing network node id to the settlement that
    landed on top of it.

    A settlement sitting on an existing node is merged rather than duplicated -
    otherwise every seed town gains a phantom twin a few hundred metres away,
    joined by a connector edge that is pure fiction.
    """
    if not network_nodes:
        return [], [], list(settlements), {}

    cell_deg = max(coincident_km, 5.0) / 111.0
    buckets = _grid_index(network_nodes, cell_deg)

    nodes: list[dict] = []
    edges: list[dict] = []
    unattached: list[Settlement] = []
    merged_into: dict[str, Settlement] = {}

    for settlement in settlements:
        node_id, distance = nearest_node(
            settlement.lat, settlement.lon, network_nodes, buckets,
            cell_deg, max_attach_km,
        )
        if node_id is None:
            unattached.append(settlement)
            continue

        if distance <= coincident_km:
            # Keep the best-populated claimant, so a named town beats a hamlet
            # tagged at the same junction.
            current = merged_into.get(node_id)
            if current is None or settlement.population > current.population:
                merged_into[node_id] = settlement
            continue

        nodes.append(
            {
                "id": settlement.node_id,
                "name": settlement.name,
                "state": "",
                "lat": round(settlement.lat, 6),
                "lon": round(settlement.lon, 6),
                "kind": settlement.place_type,
                "population": settlement.population,
                "population_known": int(settlement.population_known),
                "has_market": 0,
                "has_coldstore": 0,
            }
        )
        edges.append(
            {
                "u": settlement.node_id,
                "v": node_id,
                "mode": "road",
                "distance_km": round(max(distance * ACCESS_CIRCUITY, 0.1), 2),
                "terrain": "plain",
                "route_ref": "access",
                "lanes": 1,
                "highway": "access",
                "bridge": 0,
                "tunnel": 0,
                "surface": "",
                "osm_way_id": 0,
            }
        )

    return nodes, edges, unattached, merged_into
