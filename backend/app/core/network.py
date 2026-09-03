"""The multimodal network: loading, and the layered graph the optimiser walks.

Mode changes are not free, so the graph is layered by mode. A physical place
like Jogighopa becomes several graph nodes - ("JGP", "road"), ("JGP", "water") -
joined by transfer edges that carry the handling cost and terminal dwell of
actually moving a consignment between a truck and a barge. Routing on a flat
graph would silently give away those transhipments, which is exactly the error
that makes naive multimodal plans look better on paper than in a yard.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from functools import lru_cache

import networkx as nx

from ..config import MODES, SEED_DIR
from .costing import leg_cost, transfer_cost
from .risk import RiskModel

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    state: str
    lat: float
    lon: float
    kind: str
    population: int
    has_market: bool
    has_coldstore: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "lat": self.lat,
            "lon": self.lon,
            "kind": self.kind,
            "population": self.population,
            "has_market": self.has_market,
            "has_coldstore": self.has_coldstore,
        }


@dataclass
class Network:
    places: dict[str, Place]
    edges: list[dict] = field(default_factory=list)

    def modes_at(self, place_id: str) -> set[str]:
        return {
            e["mode"]
            for e in self.edges
            if e["u"] == place_id or e["v"] == place_id
        }

    def edge_by_id(self, edge_id: str) -> dict | None:
        return next((e for e in self.edges if e["id"] == edge_id), None)


def haversine_km(a: Place, b: Place) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


@lru_cache(maxsize=1)
def load_network() -> Network:
    """Read the seed CSVs once per process."""
    places: dict[str, Place] = {}
    with (SEED_DIR / "nodes.csv").open() as fh:
        for row in csv.DictReader(fh):
            places[row["id"]] = Place(
                id=row["id"],
                name=row["name"],
                state=row["state"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                kind=row["kind"],
                population=int(row["population"]),
                has_market=row["has_market"] == "1",
                has_coldstore=row["has_coldstore"] == "1",
            )

    edges: list[dict] = []
    with (SEED_DIR / "edges.csv").open() as fh:
        for row in csv.DictReader(fh):
            if row["u"] not in places or row["v"] not in places:
                raise ValueError(f"edge references unknown place: {row['u']}->{row['v']}")
            edges.append(
                {
                    "id": f"{row['u']}-{row['v']}-{row['mode']}",
                    "u": row["u"],
                    "v": row["v"],
                    "mode": row["mode"],
                    "distance_km": float(row["distance_km"]),
                    "terrain": row["terrain"],
                    "route_ref": row["route_ref"],
                    "lanes": int(row["lanes"]),
                    "monsoon_exposure": float(row["monsoon_exposure"]),
                    "landslide_events": int(row["landslide_events"]),
                }
            )
    return Network(places=places, edges=edges)


def build_graph(
    network: Network,
    risk_model: RiskModel,
    month: str,
    weights: dict[str, float],
    allowed_modes: set[str] | None = None,
    blocked_edge_ids: set[str] | None = None,
    value_of_time: float = 25.0,
) -> nx.DiGraph:
    """Build the mode-layered graph for one set of planning assumptions."""
    allowed = allowed_modes or set(MODES)
    blocked = blocked_edge_ids or set()

    graph = nx.DiGraph()

    for edge in network.edges:
        if edge["mode"] not in allowed or edge["id"] in blocked:
            continue
        assessment = risk_model.assess(edge, month)
        cost = leg_cost(edge, assessment, weights, value_of_time)
        attrs = {
            "edge_id": edge["id"],
            "kind": "travel",
            "mode": edge["mode"],
            "raw": edge,
            "risk": assessment,
            "cost": cost,
            "weight": cost.generalised,
        }
        a = (edge["u"], edge["mode"])
        b = (edge["v"], edge["mode"])
        # Seed edges are undirected physical links; add both directions.
        graph.add_edge(a, b, **attrs)
        graph.add_edge(b, a, **attrs)

    # Transfer edges wherever a place is served by more than one mode.
    for place_id in network.places:
        modes_here = sorted(network.modes_at(place_id) & allowed)
        for from_mode in modes_here:
            for to_mode in modes_here:
                if from_mode == to_mode:
                    continue
                a, b = (place_id, from_mode), (place_id, to_mode)
                if not (graph.has_node(a) and graph.has_node(b)):
                    continue
                cost = transfer_cost(from_mode, to_mode, weights)
                graph.add_edge(
                    a,
                    b,
                    edge_id=f"{place_id}:{from_mode}>{to_mode}",
                    kind="transfer",
                    mode=to_mode,
                    raw=None,
                    risk=None,
                    cost=cost,
                    weight=cost.generalised,
                )

    return graph


def attach_terminals(graph: nx.DiGraph, origin: str, destination: str) -> tuple[str, str]:
    """Add zero-cost super-source/sink so a trip may start or end in any mode."""
    source, sink = ("__src__", "*"), ("__dst__", "*")
    zero = {"kind": "virtual", "mode": None, "raw": None, "risk": None, "cost": None, "weight": 0.0}

    for mode in MODES:
        if graph.has_node((origin, mode)):
            graph.add_edge(source, (origin, mode), edge_id="src", **zero)
        if graph.has_node((destination, mode)):
            graph.add_edge((destination, mode), sink, edge_id="dst", **zero)
    return source, sink
