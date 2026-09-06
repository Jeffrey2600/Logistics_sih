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
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import networkx as nx

from ..config import MODES, PROCESSED_DIR, SEED_DIR
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
    _modes_cache: tuple[int, dict[str, set[str]]] | None = field(
        default=None, repr=False, compare=False
    )

    def modes_at(self, place_id: str) -> set[str]:
        return self.modes_by_place().get(place_id, set())

    def modes_by_place(self) -> dict[str, set[str]]:
        """{place_id: modes serving it}, built in one pass over the edges.

        Answering this per place by scanning every edge is quadratic, and
        build_graph asks it for every place: at 10,572 places and 11,276 edges
        that is 119 million comparisons and about fifteen seconds, which the
        seed network's 46 places hid completely.

        Cached against the edge count rather than with lru_cache: caching on
        the instance would pin every Network ever built in memory, and keying
        on identity risks a freed object's id being reused. Tests append edges
        after construction, and the count catches that.
        """
        if self._modes_cache is None or self._modes_cache[0] != len(self.edges):
            modes: dict[str, set[str]] = {}
            for edge in self.edges:
                modes.setdefault(edge["u"], set()).add(edge["mode"])
                modes.setdefault(edge["v"], set()).add(edge["mode"])
            self._modes_cache = (len(self.edges), modes)
        return self._modes_cache[1]

    def edge_by_id(self, edge_id: str) -> dict | None:
        return next((e for e in self.edges if e["id"] == edge_id), None)

    def components(self) -> list[set[str]]:
        """Connected components over all modes, largest first.

        A fragmented network is not a crash, it is worse: routing still returns
        answers for the reachable pairs while every accessibility score for an
        orphaned place is quietly wrong. It is reported at /health so a partial
        OSM build is visible before anyone trusts a number from it.
        """
        adjacency: dict[str, set[str]] = {p: set() for p in self.places}
        for edge in self.edges:
            adjacency[edge["u"]].add(edge["v"])
            adjacency[edge["v"]].add(edge["u"])

        seen: set[str] = set()
        found: list[set[str]] = []
        for start in adjacency:
            if start in seen:
                continue
            stack, component = [start], set()
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                stack.extend(adjacency[node] - component)
            seen |= component
            found.append(component)
        return sorted(found, key=len, reverse=True)


def haversine_km(a: Place, b: Place) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


OSM_NODES = PROCESSED_DIR / "osm_nodes.csv"
OSM_EDGES = PROCESSED_DIR / "osm_edges.csv"
SETTLEMENT_NODES = PROCESSED_DIR / "settlement_nodes.csv"
SETTLEMENT_EDGES = PROCESSED_DIR / "settlement_edges.csv"
SETTLEMENT_MERGES = PROCESSED_DIR / "settlement_merges.csv"

# A node the road graph invented, as opposed to a place people live in. The
# distinction has to be by kind rather than by population: OSM tags population
# on only a minority of villages, so "population == 0" would discard most real
# settlements as if they were junctions.
JUNCTION_KIND = "junction"

# Sensible defaults for attributes OSM does not carry. Landslide history comes
# from the COOLR join when it has been run; monsoon exposure is a placeholder
# that the per-place rainfall index largely supersedes anyway.
OSM_DEFAULT_MONSOON_EXPOSURE = 0.45


def _read_places(path: Path) -> dict[str, Place]:
    places: dict[str, Place] = {}
    with path.open() as fh:
        for row in csv.DictReader(fh):
            places[row["id"]] = Place(
                id=row["id"],
                name=row["name"],
                state=row.get("state", ""),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                kind=row.get("kind", "junction"),
                population=int(row.get("population") or 0),
                has_market=str(row.get("has_market", "0")) == "1",
                has_coldstore=str(row.get("has_coldstore", "0")) == "1",
            )
    return places


def _read_edges(path: Path, places: dict[str, Place], defaults: dict) -> list[dict]:
    edges: list[dict] = []
    with path.open() as fh:
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
                    "monsoon_exposure": float(
                        row.get("monsoon_exposure") or defaults["monsoon_exposure"]
                    ),
                    "landslide_events": int(row.get("landslide_events") or 0),
                }
            )
    return edges


def osm_network_available() -> bool:
    return OSM_NODES.exists() and OSM_EDGES.exists()


def use_osm() -> bool:
    """OSM is opt-in.

    The seed network is committed and known-good; the OSM build is neither, and
    a partial anchoring would silently disconnect places rather than fail
    loudly. Turning it on is therefore a deliberate act:

        NER_USE_OSM=1 uvicorn backend.app.main:app
    """
    return os.environ.get("NER_USE_OSM", "").lower() in ("1", "true", "yes") and (
        osm_network_available()
    )


def merge_settlements(net: Network, protected_ids: set[str]) -> Network:
    """Add OSM populated places, so the model knows where people actually live.

    Without this the accessibility index ranks only the 46 hand-built seed
    towns however large the road network grows, because every other node is a
    junction. Settlements arrive as nodes joined by last-mile connector edges,
    plus a merge list for those that landed on an existing node.

    `protected_ids` are never overwritten - the seed places, whose population,
    markets and cold stores are curated. An OSM `population` tag is not better
    evidence. They are passed in rather than inferred from the node kind,
    because inferring it would silently stop protecting them the moment the
    seed data grew a node kind the check did not anticipate.
    """
    if not (SETTLEMENT_NODES.exists() and SETTLEMENT_EDGES.exists()):
        return net

    places = dict(net.places)

    for place_id, place in _read_places(SETTLEMENT_NODES).items():
        if place_id not in places:
            places[place_id] = place

    if SETTLEMENT_MERGES.exists():
        with SETTLEMENT_MERGES.open() as fh:
            for row in csv.DictReader(fh):
                node_id = row["node_id"]
                existing = places.get(node_id)
                if existing is None or node_id in protected_ids:
                    continue
                # A bare junction becomes the settlement sitting on top of it.
                places[node_id] = Place(
                    id=node_id,
                    name=row["name"],
                    state=existing.state,
                    lat=existing.lat,
                    lon=existing.lon,
                    kind=row["kind"],
                    population=int(row.get("population") or 0),
                    has_market=existing.has_market,
                    has_coldstore=existing.has_coldstore,
                )

    edges = list(net.edges)
    for edge in _read_edges(SETTLEMENT_EDGES, places,
                            {"monsoon_exposure": OSM_DEFAULT_MONSOON_EXPOSURE}):
        edges.append(edge)

    return Network(places=places, edges=edges)


def merge_osm(seed: Network, osm: Network) -> Network:
    """Union the OSM road graph with the seed's rail, water and air links.

    OSM ingestion produces roads only. Rail alignments, the NW-2 waterway and
    air links stay from the seed network, and they connect because the seed
    places they reference are anchored into the OSM graph during ingestion.

    Seed *road* edges are dropped: keeping both would offer the optimiser two
    parallel descriptions of the same highway, one coarse and one detailed, and
    it would take whichever the assumptions happened to favour.

    Every seed place is retained even when OSM ingestion did not anchor it. A
    place the road graph missed may still be genuinely served by rail - Lumding
    is exactly that - and dropping it would lose a real link. What it must not
    do is disappear silently, which is why /health reports connectivity.
    """
    # Seed metadata wins: it carries population, markets and cold stores, which
    # bare OSM junctions do not have.
    places = {**osm.places, **seed.places}
    edges = list(osm.edges) + [e for e in seed.edges if e["mode"] != "road"]
    return Network(places=places, edges=edges)


@lru_cache(maxsize=1)
def load_network() -> Network:
    """The active network: seed by default, seed+OSM when NER_USE_OSM is set."""
    seed = Network(
        places=(seed_places := _read_places(SEED_DIR / "nodes.csv")),
        edges=_read_edges(SEED_DIR / "edges.csv", seed_places,
                          {"monsoon_exposure": 0.3}),
    )
    if not use_osm():
        return seed

    osm_places = _read_places(OSM_NODES)
    osm = Network(
        places=osm_places,
        edges=_read_edges(OSM_EDGES, osm_places,
                          {"monsoon_exposure": OSM_DEFAULT_MONSOON_EXPOSURE}),
    )
    return merge_settlements(merge_osm(seed, osm), set(seed.places))


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
    modes_by_place = network.modes_by_place()
    for place_id in network.places:
        modes_here = sorted(modes_by_place.get(place_id, set()) & allowed)
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


# Graphs are cached, so anything that mutates one must undo itself. The cache is
# small on purpose: each entry is a whole layered graph, and at OSM scale that is
# tens of thousands of nodes.
_GRAPH_CACHE: dict[tuple, nx.DiGraph] = {}
_GRAPH_CACHE_MAX = 6


def cached_graph(
    network: Network,
    risk_model: RiskModel,
    month: str,
    weights: dict[str, float],
    allowed_modes: set[str] | None = None,
    blocked_edge_ids: set[str] | None = None,
    value_of_time: float = 25.0,
) -> nx.DiGraph:
    """build_graph, memoised on everything that changes the result.

    Rebuilding the layered graph per request costs seconds once the network
    comes from OSM. The accessibility index in particular asks for the same
    time-weighted graph over and over, so it hits this cache every time after
    the first.
    """
    key = (
        id(network),
        risk_model.name,
        month.lower()[:3],
        tuple(sorted(weights.items())),
        tuple(sorted(allowed_modes or MODES)),
        tuple(sorted(blocked_edge_ids or ())),
        value_of_time,
    )
    graph = _GRAPH_CACHE.get(key)
    if graph is None:
        graph = build_graph(
            network, risk_model, month, weights,
            allowed_modes=allowed_modes,
            blocked_edge_ids=blocked_edge_ids,
            value_of_time=value_of_time,
        )
        if len(_GRAPH_CACHE) >= _GRAPH_CACHE_MAX:
            _GRAPH_CACHE.pop(next(iter(_GRAPH_CACHE)))
        _GRAPH_CACHE[key] = graph
    return graph


def clear_graph_cache() -> None:
    _GRAPH_CACHE.clear()


def attach_terminals(graph: nx.DiGraph, origin: str, destination: str) -> tuple[str, str]:
    """Add zero-cost super-source/sink so a trip may start or end in any mode.

    Mutates the graph, which is now shared via the cache, so every caller must
    pair this with `detach_terminals`.
    """
    source, sink = ("__src__", "*"), ("__dst__", "*")
    zero = {"kind": "virtual", "mode": None, "raw": None, "risk": None, "cost": None, "weight": 0.0}

    for mode in MODES:
        if graph.has_node((origin, mode)):
            graph.add_edge(source, (origin, mode), edge_id="src", **zero)
        if graph.has_node((destination, mode)):
            graph.add_edge((destination, mode), sink, edge_id="dst", **zero)
    return source, sink


def detach_terminals(graph: nx.DiGraph, source, sink) -> None:
    """Remove the virtual terminals, restoring a cached graph exactly."""
    graph.remove_nodes_from([source, sink])
