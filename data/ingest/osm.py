"""Turn raw OpenStreetMap ways into a routable network.

This module is deliberately free of network access. Everything here is a pure
transformation of an Overpass JSON payload, so the part of OSM ingestion where
the bugs actually live is testable without the internet.

The hard part is not downloading OSM. It is that OSM is a drawing, not a graph:
a single national highway is hundreds of `way` objects, each with dozens of
geometry nodes that exist only to trace a curve. Routing over those raw nodes
would produce a graph two orders of magnitude larger than the problem needs and
still not know where the junctions are. So the pipeline is:

1. Parse ways and their geometry.
2. Decide which nodes are *interesting*: junctions between ways, way endpoints,
   and the seed places we already model.
3. Split every way at those nodes and contract the chains between them into a
   single edge, summing the real traced length rather than the straight line.
4. Infer the attributes the risk and cost models need from tags and geometry.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from common import haversine_km

# Highway classes worth modelling for freight. Residential streets and tracks
# are noise at this scale and would swamp the graph.
HIGHWAY_CLASSES = (
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "motorway_link", "trunk_link", "primary_link",
)

# Default carriageway width by class, used when the `lanes` tag is absent -
# which in the NER it usually is.
DEFAULT_LANES = {
    "motorway": 4, "trunk": 2, "primary": 2, "secondary": 2, "tertiary": 1,
    "motorway_link": 2, "trunk_link": 2, "primary_link": 2,
}

# Sinuosity - traced length over straight-line chord - as a terrain proxy.
# A road that wanders 40% further than the chord is climbing something. This
# needs no elevation model, which matters because DEM APIs are rate-limited
# and often unreachable, but it is a proxy: a straight road across a high
# plateau reads as plain. `elevation_profile` can override it when a DEM is
# available.
SINUOSITY_HILLY = 1.15
SINUOSITY_MOUNTAIN = 1.35

# Below this, sinuosity is dominated by how finely the way happens to be
# traced rather than by terrain, so it is not trusted.
MIN_LENGTH_FOR_SINUOSITY_KM = 3.0

# Nodes closer together than this collapse into one. OSM splits a highway at
# every change of tagging, so junctions are routinely surrounded by stubs a few
# metres long. Those stubs are artefacts of how the road is *drawn*, not
# separate links, and each one left in place is a degree-1 node hanging off the
# graph. Deleting them instead of merging them would be worse still: an edge
# carries connectivity, so dropping a 30 m link severs whatever it joined.
DEFAULT_NODE_MERGE_METRES = 75.0

# How close an OSM node must be to a seed place to *be* that place.
DEFAULT_SNAP_RADIUS_KM = 12.0

# Every node within this distance of a seed place collapses into it. OSM
# routinely carries several coincident-but-distinct nodes where roads meet a
# town - separate carriageways, untagged duplicates, ways that simply do not
# share an endpoint. Anchoring only the single nearest one leaves the others as
# separate junctions metres away, which fragments the graph at precisely the
# places the model cares most about. Merging also drops intra-town streets that
# are noise at freight scale.
DEFAULT_MERGE_RADIUS_KM = 2.0


@dataclass
class Way:
    id: int
    tags: dict
    node_ids: list[int]
    geometry: list[tuple[float, float]]  # (lat, lon), parallel to node_ids

    @property
    def highway(self) -> str:
        return self.tags.get("highway", "")


@dataclass
class Chain:
    """A run of geometry between two interesting nodes."""

    way: Way
    node_ids: list[int]
    geometry: list[tuple[float, float]]

    @property
    def start(self) -> int:
        return self.node_ids[0]

    @property
    def end(self) -> int:
        return self.node_ids[-1]

    def traced_length_km(self) -> float:
        return sum(
            haversine_km(a[0], a[1], b[0], b[1])
            for a, b in zip(self.geometry, self.geometry[1:])
        )

    def chord_km(self) -> float:
        first, last = self.geometry[0], self.geometry[-1]
        return haversine_km(first[0], first[1], last[0], last[1])


@dataclass
class OsmNetwork:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)


def parse_overpass(payload: dict) -> list[Way]:
    """Read ways out of an Overpass `out body geom` response.

    Elements missing geometry or with fewer than two nodes are skipped rather
    than raising: a partial Overpass response is common under load and must not
    abort an ingest that is otherwise fine.
    """
    ways: list[Way] = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry") or []
        node_ids = element.get("nodes") or []
        if len(geometry) < 2 or len(geometry) != len(node_ids):
            continue
        ways.append(
            Way(
                id=element["id"],
                tags=element.get("tags", {}) or {},
                node_ids=list(node_ids),
                geometry=[(point["lat"], point["lon"]) for point in geometry],
            )
        )
    return ways


def find_interesting_nodes(ways: list[Way], anchors: set[int]) -> set[int]:
    """Junctions, way endpoints and anchored seed places.

    A node shared by two or more ways is a junction. Endpoints matter even when
    unshared, or a dead-end spur would be silently dropped.
    """
    appearances: Counter[int] = Counter()
    for way in ways:
        # Count each node once per way, so a way that loops back on itself does
        # not fake a junction with itself.
        for node_id in set(way.node_ids):
            appearances[node_id] += 1

    interesting = {node_id for node_id, count in appearances.items() if count >= 2}
    for way in ways:
        interesting.add(way.node_ids[0])
        interesting.add(way.node_ids[-1])
    return interesting | (anchors & set(appearances))


def split_into_chains(ways: list[Way], interesting: set[int]) -> list[Chain]:
    """Cut each way at every interesting node."""
    chains: list[Chain] = []
    for way in ways:
        current_ids = [way.node_ids[0]]
        current_geom = [way.geometry[0]]
        for node_id, point in zip(way.node_ids[1:], way.geometry[1:]):
            current_ids.append(node_id)
            current_geom.append(point)
            if node_id in interesting:
                if len(current_ids) >= 2 and current_ids[0] != current_ids[-1]:
                    chains.append(Chain(way, current_ids, current_geom))
                current_ids = [node_id]
                current_geom = [point]
    return chains


def classify_terrain(length_km: float, chord_km: float) -> str:
    """Terrain band from sinuosity, with a guard for very short chains."""
    if length_km < MIN_LENGTH_FOR_SINUOSITY_KM or chord_km <= 0:
        return "plain"
    sinuosity = length_km / chord_km
    if sinuosity >= SINUOSITY_MOUNTAIN:
        return "mountain"
    if sinuosity >= SINUOSITY_HILLY:
        return "hilly"
    return "plain"


def lanes_from_tags(tags: dict) -> int:
    """Explicit `lanes` tag when present and sane, else the class default."""
    raw = tags.get("lanes")
    if raw is not None:
        try:
            # OSM carries values like "2", "2;3" and " 2 ". Take the first.
            lanes = int(float(str(raw).split(";")[0].strip()))
            if 1 <= lanes <= 8:
                # `lanes` counts both directions; the cost model wants the
                # carriageway class, so a 4-lane divided road stays 4.
                return lanes
        except (TypeError, ValueError):
            pass
    return DEFAULT_LANES.get(tags.get("highway", ""), 2)


def route_ref_from_tags(tags: dict) -> str:
    """Prefer a national highway reference, else any ref, else the class."""
    for key in ("ref", "nat_ref", "int_ref"):
        value = tags.get(key)
        if value:
            return str(value).split(";")[0].strip()
    return tags.get("highway", "road")


def snap_anchors(
    ways: list[Way],
    places: dict[str, dict],
    radius_km: float = DEFAULT_SNAP_RADIUS_KM,
    merge_radius_km: float = DEFAULT_MERGE_RADIUS_KM,
) -> dict[int, str]:
    """Map OSM node ids onto seed place ids where they coincide.

    Anchoring matters for continuity: without it the OSM network and the
    hand-built seed network would be two disjoint graphs sharing no node, and
    every accessibility score computed against seed facilities would be
    unreachable.

    Two radii, doing different jobs. Every node within `merge_radius_km` of a
    place collapses into it, which both merges OSM's coincident duplicates and
    discards intra-town streets. If nothing falls inside that, the single
    nearest node within `radius_km` is anchored instead, so a town set back
    from the highway still joins the network at its closest point.

    A node inside two places' merge radii goes to the nearer one.
    """
    candidates: dict[int, tuple[float, float]] = {}
    for way in ways:
        for node_id, point in zip(way.node_ids, way.geometry):
            candidates[node_id] = point

    # node_id -> (distance, place_id), keeping the closest claim.
    claims: dict[int, tuple[float, str]] = {}

    for place_id, place in places.items():
        lat, lon = float(place["lat"]), float(place["lon"])
        distances = {
            node_id: haversine_km(lat, lon, node_lat, node_lon)
            for node_id, (node_lat, node_lon) in candidates.items()
        }
        within = {n: d for n, d in distances.items() if d <= merge_radius_km}

        if not within:
            nearest = min(distances.items(), key=lambda kv: kv[1], default=None)
            if nearest is None or nearest[1] > radius_km:
                continue
            within = {nearest[0]: nearest[1]}

        for node_id, distance in within.items():
            if node_id not in claims or distance < claims[node_id][0]:
                claims[node_id] = (distance, place_id)

    return {node_id: place_id for node_id, (_distance, place_id) in claims.items()}


def _node_name(node_id: int, anchored: dict[int, str]) -> str:
    return anchored.get(node_id) or f"n{node_id}"


def cluster_nodes(
    coordinates: dict[int, tuple[float, float]],
    merge_metres: float = DEFAULT_NODE_MERGE_METRES,
) -> dict[int, int]:
    """Group nodes within `merge_metres` of each other; return node -> leader.

    Uses union-find over a spatial grid, so only nodes in neighbouring cells are
    ever compared and the pass stays linear in the number of nodes rather than
    quadratic. That matters: a full NER extract carries hundreds of thousands.
    """
    parent: dict[int, int] = {node_id: node_id for node_id in coordinates}

    def find(node_id: int) -> int:
        root = node_id
        while parent[root] != root:
            root = parent[root]
        while parent[node_id] != root:      # path compression
            parent[node_id], node_id = root, parent[node_id]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            # Keep the smaller id as leader so the result is deterministic.
            parent[max(ra, rb)] = min(ra, rb)

    merge_km = merge_metres / 1000.0
    cell = merge_km / 111.0                 # degrees, roughly, at this latitude

    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for node_id, (lat, lon) in coordinates.items():
        buckets[(int(lat / cell), int(lon / cell))].append(node_id)

    for (row, col), members in buckets.items():
        neighbours: list[int] = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                neighbours.extend(buckets.get((row + dr, col + dc), ()))
        for node_id in members:
            lat, lon = coordinates[node_id]
            for other in neighbours:
                if other <= node_id:
                    continue
                other_lat, other_lon = coordinates[other]
                if haversine_km(lat, lon, other_lat, other_lon) <= merge_km:
                    union(node_id, other)

    return {node_id: find(node_id) for node_id in coordinates}


def build_network(
    payload: dict,
    places: dict[str, dict],
    snap_radius_km: float = DEFAULT_SNAP_RADIUS_KM,
    merge_radius_km: float = DEFAULT_MERGE_RADIUS_KM,
    node_merge_metres: float = DEFAULT_NODE_MERGE_METRES,
    min_edge_km: float = 0.0,
) -> OsmNetwork:
    """Full pipeline: Overpass payload in, routable network out.

    `min_edge_km` defaults to zero on purpose. Filtering short edges looks like
    tidying and is actually destructive: an edge is the only thing carrying
    connectivity, so dropping the stubs OSM leaves around junctions shatters the
    graph. Short links are collapsed by `cluster_nodes` instead.
    """
    ways = [w for w in parse_overpass(payload) if w.highway in HIGHWAY_CLASSES]
    if not ways:
        return OsmNetwork()

    anchored = snap_anchors(ways, places, snap_radius_km, merge_radius_km)
    interesting = find_interesting_nodes(ways, set(anchored))
    chains = split_into_chains(ways, interesting)

    coordinates: dict[int, tuple[float, float]] = {}
    for way in ways:
        for node_id, point in zip(way.node_ids, way.geometry):
            coordinates[node_id] = point

    # Collapse coincident nodes before naming anything, so the stubs OSM leaves
    # around junctions merge away instead of hanging off the graph.
    leader = cluster_nodes(coordinates, node_merge_metres)

    # An anchored place claims its whole cluster: if any node in the cluster is
    # a seed place, the cluster *is* that place.
    cluster_place: dict[int, str] = {}
    for node_id, place_id in anchored.items():
        cluster_place.setdefault(leader[node_id], place_id)

    def name_of(node_id: int) -> str:
        root = leader[node_id]
        return cluster_place.get(root) or f"n{root}"

    # Keep only the shortest edge between any pair, so dual carriageways mapped
    # as two ways collapse into one link rather than a spurious parallel route.
    best: dict[tuple[str, str], dict] = {}
    for chain in chains:
        length = chain.traced_length_km()
        if length < min_edge_km:
            continue

        u = name_of(chain.start)
        v = name_of(chain.end)
        if u == v:
            continue

        key = (u, v) if u < v else (v, u)
        tags = chain.way.tags
        edge = {
            "u": key[0],
            "v": key[1],
            "mode": "road",
            "distance_km": round(length, 2),
            "terrain": classify_terrain(length, chain.chord_km()),
            "route_ref": route_ref_from_tags(tags),
            "lanes": lanes_from_tags(tags),
            "highway": tags.get("highway", ""),
            "bridge": int(bool(tags.get("bridge"))),
            "tunnel": int(bool(tags.get("tunnel"))),
            "surface": tags.get("surface", ""),
            "osm_way_id": chain.way.id,
        }
        if key not in best or edge["distance_km"] < best[key]["distance_km"]:
            best[key] = edge

    edges = sorted(best.values(), key=lambda e: (e["u"], e["v"]))

    used_nodes = {e["u"] for e in edges} | {e["v"] for e in edges}
    representative: dict[str, int] = {}
    for node_id in coordinates:
        representative.setdefault(name_of(node_id), node_id)

    nodes: dict[str, dict] = {}
    for name in sorted(used_nodes):
        lat, lon = coordinates[representative[name]]
        seed = places.get(name)
        nodes[name] = {
            "id": name,
            "name": seed["name"] if seed else name,
            "state": seed["state"] if seed else "",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "kind": seed["kind"] if seed else "junction",
            "population": int(seed["population"]) if seed else 0,
            "has_market": int(seed["has_market"]) if seed else 0,
            "has_coldstore": int(seed["has_coldstore"]) if seed else 0,
        }

    return OsmNetwork(nodes=nodes, edges=edges)


def degree_histogram(network: OsmNetwork) -> dict[int, int]:
    """Node degree distribution - a fast sanity check on a built network.

    A healthy road network is mostly degree 2 and 3. A flood of degree-1 nodes
    means ways are not being joined and the graph is shattered.
    """
    degree: Counter[str] = Counter()
    for edge in network.edges:
        degree[edge["u"]] += 1
        degree[edge["v"]] += 1
    histogram: dict[int, int] = defaultdict(int)
    for count in degree.values():
        histogram[count] += 1
    return dict(sorted(histogram.items()))


def largest_component(network: OsmNetwork) -> set[str]:
    """Nodes in the biggest connected component."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in network.edges:
        adjacency[edge["u"]].add(edge["v"])
        adjacency[edge["v"]].add(edge["u"])

    seen: set[str] = set()
    biggest: set[str] = set()
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
        if len(component) > len(biggest):
            biggest = component
    return biggest
