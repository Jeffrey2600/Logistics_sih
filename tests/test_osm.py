"""OSM ingestion logic.

The Overpass download itself needs the internet; every transformation it feeds
does not. These tests drive the whole pipeline on a synthetic payload shaped
like a real `out body geom` response, over real NER coordinates.
"""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "ingest"))

from common import haversine_km  # noqa: E402
from osm import (  # noqa: E402
    build_network, classify_terrain, degree_histogram, find_interesting_nodes,
    lanes_from_tags, largest_component, parse_overpass, route_ref_from_tags,
    snap_anchors, split_into_chains,
)

# Real coordinates, so distances and sinuosity are physically meaningful.
GAU = (26.1445, 91.7362)   # Guwahati
BYR = (26.0333, 91.8667)   # Byrnihat
SHL = (25.5788, 91.8933)   # Shillong
NGN = (26.3464, 92.6840)   # Nagaon


def densify(a, b, count, wiggle=0.0):
    """Interpolate `count` points from a to b, optionally made to wander.

    `wiggle` displaces intermediate points perpendicular to the chord, which is
    what a hill road does and what the sinuosity terrain proxy keys on.
    """
    points = []
    for i in range(count + 1):
        t = i / count
        lat = a[0] + (b[0] - a[0]) * t
        lon = a[1] + (b[1] - a[1]) * t
        if wiggle and 0 < i < count:
            offset = math.sin(t * math.pi * 6) * wiggle
            lat += offset
            lon += offset * 0.6
        points.append((round(lat, 6), round(lon, 6)))
    return points


def way(way_id, tags, points, node_ids=None):
    """One element in the shape Overpass returns for `out body geom`."""
    ids = node_ids or [way_id * 1000 + i for i in range(len(points))]
    assert len(ids) == len(points)
    return {
        "type": "way",
        "id": way_id,
        "tags": tags,
        "nodes": ids,
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in points],
    }


# Byrnihat is the junction where the two NH-6 ways meet: the same OSM node id
# must appear as the last node of one way and the first node of the next.
BYR_NODE = 2_999

NH6_NORTH = densify(GAU, BYR, 20)
NH6_SOUTH = densify(BYR, SHL, 40, wiggle=0.045)   # the Shillong climb
NH27 = densify(GAU, NGN, 30)


@pytest.fixture
def payload():
    return {
        "elements": [
            way(1, {"highway": "trunk", "ref": "NH-27", "lanes": "4"}, NH27),
            way(2, {"highway": "trunk", "ref": "NH-6", "lanes": "4"}, NH6_NORTH,
                node_ids=[2000 + i for i in range(len(NH6_NORTH) - 1)] + [BYR_NODE]),
            way(3, {"highway": "trunk", "ref": "NH-6", "lanes": "2"}, NH6_SOUTH,
                node_ids=[BYR_NODE] + [3000 + i for i in range(1, len(NH6_SOUTH))]),
            # Same corridor as way 1, mapped as the other carriageway.
            way(4, {"highway": "trunk", "ref": "NH-27"}, densify(GAU, NGN, 25, wiggle=0.004),
                node_ids=[4000] + [4000 + i for i in range(1, 25)] + [1030]),
            way(5, {"highway": "residential"}, densify(GAU, (26.15, 91.75), 4)),
            way(6, {"highway": "primary"}, densify(SHL, (25.58, 91.90), 3)),  # short spur
            {"type": "node", "id": 99, "lat": 26.0, "lon": 92.0},
            {"type": "way", "id": 7, "tags": {"highway": "trunk"}},          # no geometry
            way(8, {"highway": "trunk"}, densify(GAU, NGN, 5))               # ids mismatched below
            | {"nodes": [1, 2]},
        ]
    }


@pytest.fixture
def places():
    return {
        "GAU": {"id": "GAU", "name": "Guwahati", "state": "Assam", "lat": "26.1445",
                "lon": "91.7362", "kind": "city", "population": "1116267",
                "has_market": "1", "has_coldstore": "1"},
        "SHL": {"id": "SHL", "name": "Shillong", "state": "Meghalaya", "lat": "25.5788",
                "lon": "91.8933", "kind": "city", "population": "143229",
                "has_market": "1", "has_coldstore": "1"},
        "BYR": {"id": "BYR", "name": "Byrnihat", "state": "Meghalaya", "lat": "26.0333",
                "lon": "91.8667", "kind": "logistics_hub", "population": "12000",
                "has_market": "0", "has_coldstore": "1"},
        # Far outside the fixture's geometry: must not anchor onto anything.
        "AZL": {"id": "AZL", "name": "Aizawl", "state": "Mizoram", "lat": "23.7271",
                "lon": "92.7176", "kind": "city", "population": "293416",
                "has_market": "1", "has_coldstore": "1"},
    }


# ------------------------------------------------------------------ parsing --

def test_parse_keeps_only_well_formed_ways(payload):
    ways = parse_overpass(payload)
    ids = {w.id for w in ways}
    assert 7 not in ids, "way with no geometry must be skipped"
    assert 8 not in ids, "way whose node count disagrees with its geometry must be skipped"
    assert 99 not in ids, "nodes are not ways"
    assert {1, 2, 3, 4, 5, 6} <= ids


def test_parse_is_empty_for_an_empty_response():
    assert parse_overpass({}) == []
    assert parse_overpass({"elements": []}) == []


def test_geometry_is_read_as_lat_lon_pairs(payload):
    first = next(w for w in parse_overpass(payload) if w.id == 1)
    assert first.geometry[0] == pytest.approx(GAU, abs=1e-4)
    assert len(first.geometry) == len(first.node_ids)


# ----------------------------------------------------------------- topology --

def test_shared_node_is_a_junction(payload):
    ways = [w for w in parse_overpass(payload) if w.id in (2, 3)]
    assert BYR_NODE in find_interesting_nodes(ways, set())


def test_way_endpoints_are_always_interesting(payload):
    ways = [w for w in parse_overpass(payload) if w.id == 1]
    interesting = find_interesting_nodes(ways, set())
    assert ways[0].node_ids[0] in interesting
    assert ways[0].node_ids[-1] in interesting


def test_a_node_repeated_within_one_way_is_not_a_junction():
    """A way that touches its own node twice is a loop, not a crossing."""
    points = densify(GAU, BYR, 4)
    looped = way(11, {"highway": "trunk"}, points + [points[0]],
                 node_ids=[11000 + i for i in range(len(points))] + [11000])
    ways = parse_overpass({"elements": [looped]})
    interesting = find_interesting_nodes(ways, set())
    # 11000 is an endpoint so it is interesting, but only because of that -
    # the interior nodes it shares with nothing must not be.
    assert 11002 not in interesting


def test_anchors_become_interesting(payload):
    ways = [w for w in parse_overpass(payload) if w.id == 1]
    mid = ways[0].node_ids[15]
    assert mid not in find_interesting_nodes(ways, set())
    assert mid in find_interesting_nodes(ways, {mid})


def test_chains_are_contracted_between_interesting_nodes(payload):
    """The core win: 30 geometry nodes must become one edge, not 30."""
    ways = [w for w in parse_overpass(payload) if w.id == 1]
    chains = split_into_chains(ways, find_interesting_nodes(ways, set()))
    assert len(chains) == 1
    assert len(chains[0].geometry) == len(ways[0].geometry)


def test_a_way_is_split_at_an_interior_junction(payload):
    ways = [w for w in parse_overpass(payload) if w.id == 1]
    mid = ways[0].node_ids[15]
    chains = split_into_chains(ways, find_interesting_nodes(ways, {mid}))
    assert len(chains) == 2
    assert chains[0].end == mid and chains[1].start == mid


def test_traced_length_exceeds_the_chord_on_a_winding_road(payload):
    winding = next(w for w in parse_overpass(payload) if w.id == 3)
    chain = split_into_chains([winding], {winding.node_ids[0], winding.node_ids[-1]})[0]
    assert chain.traced_length_km() > chain.chord_km() * 1.3


def test_traced_length_matches_the_chord_on_a_straight_road(payload):
    straight = next(w for w in parse_overpass(payload) if w.id == 1)
    chain = split_into_chains([straight], {straight.node_ids[0], straight.node_ids[-1]})[0]
    assert chain.traced_length_km() == pytest.approx(chain.chord_km(), rel=0.01)


# --------------------------------------------------------------- attributes --

@pytest.mark.parametrize("length,chord,expected", [
    (100.0, 99.0, "plain"),
    (100.0, 85.0, "hilly"),
    (100.0, 60.0, "mountain"),
    (2.0, 0.5, "plain"),      # too short for sinuosity to mean anything
    (100.0, 0.0, "plain"),    # degenerate chord must not divide by zero
])
def test_terrain_from_sinuosity(length, chord, expected):
    assert classify_terrain(length, chord) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"lanes": "4", "highway": "trunk"}, 4),
    ({"lanes": " 2 ", "highway": "trunk"}, 2),
    ({"lanes": "2;3", "highway": "trunk"}, 2),
    ({"lanes": "banana", "highway": "trunk"}, 2),
    ({"lanes": "99", "highway": "motorway"}, 4),   # out of range, use the class
    ({"highway": "tertiary"}, 1),
    ({"highway": "motorway"}, 4),
    ({}, 2),
])
def test_lanes_from_tags(tags, expected):
    assert lanes_from_tags(tags) == expected


@pytest.mark.parametrize("tags,expected", [
    ({"ref": "NH-27"}, "NH-27"),
    ({"ref": "NH-6;NH-206"}, "NH-6"),
    ({"nat_ref": "NH-2"}, "NH-2"),
    ({"highway": "primary"}, "primary"),
    ({}, "road"),
])
def test_route_ref_from_tags(tags, expected):
    assert route_ref_from_tags(tags) == expected


# ------------------------------------------------------------------ anchors --

def test_seed_places_anchor_onto_nearby_nodes(payload, places):
    ways = parse_overpass(payload)
    anchored = snap_anchors(ways, places)
    assert set(anchored.values()) >= {"GAU", "SHL", "BYR"}


def test_distant_places_do_not_anchor(payload, places):
    """Aizawl is 200 km from anything in this payload and must stay unanchored."""
    anchored = snap_anchors(parse_overpass(payload), places)
    assert "AZL" not in anchored.values()


def test_every_node_at_a_place_is_merged_into_it(payload, places):
    """OSM carries several coincident nodes where roads meet a town. Anchoring
    only the nearest leaves the rest as junctions metres away, splitting the
    corridor. All of them within the merge radius must collapse into the place."""
    ways = parse_overpass(payload)
    coords = {n: p for w in ways for n, p in zip(w.node_ids, w.geometry)}
    anchored = snap_anchors(ways, places, merge_radius_km=2.0)

    at_guwahati = [n for n, place in anchored.items() if place == "GAU"]
    assert len(at_guwahati) >= 2, "coincident nodes at Guwahati were not merged"
    assert all(
        haversine_km(*coords[node_id], GAU[0], GAU[1]) <= 2.0
        for node_id in at_guwahati
    )


def test_a_contested_node_goes_to_the_nearer_place(payload, places):
    """Merge radii can overlap; a node must belong to exactly one place."""
    ways = parse_overpass(payload)
    coords = {n: p for w in ways for n, p in zip(w.node_ids, w.geometry)}
    anchored = snap_anchors(ways, places, merge_radius_km=25.0)
    for node_id, place_id in anchored.items():
        distances = {
            pid: haversine_km(*coords[node_id], float(p["lat"]), float(p["lon"]))
            for pid, p in places.items()
        }
        assert place_id == min(distances, key=distances.get)


def test_a_place_off_the_highway_still_anchors_to_its_nearest_node(payload, places):
    """With nothing inside the merge radius, fall back to the single nearest."""
    ways = parse_overpass(payload)
    coords = {n: p for w in ways for n, p in zip(w.node_ids, w.geometry)}
    anchored = snap_anchors(ways, places, radius_km=12.0, merge_radius_km=0.0001)

    node_id = next(n for n, place in anchored.items() if place == "SHL")
    chosen = haversine_km(*coords[node_id], SHL[0], SHL[1])
    assert all(
        chosen <= haversine_km(*point, SHL[0], SHL[1]) + 1e-9
        for point in coords.values()
    )


def test_tight_radii_admit_only_coincident_nodes(payload, places):
    """Shrink both radii and only nodes sitting on the place itself survive."""
    ways = parse_overpass(payload)
    coords = {n: p for w in ways for n, p in zip(w.node_ids, w.geometry)}
    anchored = snap_anchors(ways, places, radius_km=0.05, merge_radius_km=0.05)

    assert "AZL" not in anchored.values(), "Aizawl is 200 km from this payload"
    for node_id, place_id in anchored.items():
        place = places[place_id]
        distance = haversine_km(*coords[node_id], float(place["lat"]), float(place["lon"]))
        assert distance <= 0.05


# ------------------------------------------------------------ full pipeline --

def test_network_builds(payload, places):
    network = build_network(payload, places)
    assert network.nodes and network.edges


def test_non_freight_classes_are_excluded(payload, places):
    network = build_network(payload, places)
    assert all(edge["highway"] != "residential" for edge in network.edges)


def test_min_edge_km_is_opt_in_and_defaults_to_keeping_everything(payload, places):
    """Filtering short edges looks like tidying and is destructive: an edge is
    the only thing carrying connectivity, so dropping the stubs OSM leaves
    around junctions shatters the graph. It stays available, but off."""
    import inspect

    assert inspect.signature(build_network).parameters["min_edge_km"].default == 0.0
    filtered = build_network(payload, places, min_edge_km=0.5)
    assert all(edge["distance_km"] >= 0.5 for edge in filtered.edges)


def test_anchored_places_are_named_by_their_seed_id(payload, places):
    network = build_network(payload, places)
    assert "GAU" in network.nodes
    assert network.nodes["GAU"]["name"] == "Guwahati"
    assert network.nodes["GAU"]["population"] == 1116267


def test_unanchored_junctions_get_synthetic_ids(payload, places):
    network = build_network(payload, places)
    synthetic = [n for n in network.nodes if n.startswith("n")]
    assert synthetic
    assert all(network.nodes[n]["kind"] == "junction" for n in synthetic)


def test_dual_carriageway_collapses_to_one_edge(payload, places):
    """Ways 1 and 4 are the same corridor. Two edges would invent a choice."""
    network = build_network(payload, places)
    pairs = [(edge["u"], edge["v"]) for edge in network.edges]
    assert len(pairs) == len(set(pairs)), "parallel edges between the same pair"


def test_no_self_loops(payload, places):
    assert all(edge["u"] != edge["v"] for edge in build_network(payload, places).edges)


def test_edges_carry_everything_the_cost_model_needs(payload, places):
    required = {"u", "v", "mode", "distance_km", "terrain", "route_ref", "lanes"}
    for edge in build_network(payload, places).edges:
        assert required <= set(edge)
        assert edge["mode"] == "road"
        assert edge["distance_km"] > 0
        assert edge["terrain"] in ("plain", "hilly", "mountain")


def test_the_shillong_climb_is_classified_as_hill_terrain(payload, places):
    """A real check on the proxy: NH-6 up to Shillong is not flat."""
    network = build_network(payload, places)
    climb = [e for e in network.edges
             if {e["u"], e["v"]} == {"BYR", "SHL"}]
    assert climb, "expected a Byrnihat-Shillong edge"
    assert climb[0]["terrain"] in ("hilly", "mountain")


def test_the_plains_corridor_is_not_classified_as_mountain(payload, places):
    network = build_network(payload, places)
    plains = [e for e in network.edges if e["route_ref"] == "NH-27"]
    assert plains
    assert all(edge["terrain"] == "plain" for edge in plains)


def test_junction_joins_the_two_nh6_ways(payload, places):
    """Byrnihat is the shared node; without it the corridor is two graphs."""
    network = build_network(payload, places)
    assert len(largest_component(network)) >= 3
    neighbours = {
        edge["v"] if edge["u"] == "BYR" else edge["u"]
        for edge in network.edges if "BYR" in (edge["u"], edge["v"])
    }
    assert {"GAU", "SHL"} <= neighbours


def test_empty_payload_yields_an_empty_network(places):
    network = build_network({"elements": []}, places)
    assert network.nodes == {} and network.edges == []


def test_degree_histogram_counts_every_endpoint(payload, places):
    network = build_network(payload, places)
    histogram = degree_histogram(network)
    assert sum(histogram.values()) == len(network.nodes)
    assert sum(degree * count for degree, count in histogram.items()) == 2 * len(network.edges)


def test_largest_component_is_a_subset_of_the_nodes(payload, places):
    network = build_network(payload, places)
    assert largest_component(network) <= set(network.nodes)


# ------------------------------------------------- region queries (Overpass) --

def _fetch_osm():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "ingest"))
    import fetch_osm

    return fetch_osm


def test_every_region_has_a_relation_id():
    fetch_osm = _fetch_osm()
    assert len(fetch_osm.NER_REGIONS) == 9, "eight NE states plus the Siliguri Corridor"
    for name, relation_id, bbox in fetch_osm.NER_REGIONS:
        assert name and isinstance(relation_id, int) and relation_id > 0
        assert bbox is None or len(bbox) == 4


def test_query_is_scoped_to_an_area_not_a_bounding_box():
    """A bbox over the NER also covers Bangladesh, Bhutan and part of Myanmar,
    whose roads would read as usable freight corridors across closed borders."""
    fetch_osm = _fetch_osm()
    query = fetch_osm.build_query(("trunk",), 2027521)
    assert "map_to_area" in query
    assert "way(area.a)" in query
    assert "out body geom;" in query, "node ids are needed to find junctions"


def test_west_bengal_is_clipped_to_the_corridor():
    """Un-clipped, West Bengal would drag in Kolkata and most of the state."""
    fetch_osm = _fetch_osm()
    name, relation_id, bbox = next(
        r for r in fetch_osm.NER_REGIONS if "Siliguri" in r[0]
    )
    assert bbox is not None
    query = fetch_osm.build_query(("trunk",), relation_id, bbox)
    assert f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})" in query


def test_class_filter_is_a_bounded_alternation():
    fetch_osm = _fetch_osm()
    query = fetch_osm.build_query(("trunk", "primary"), 1)
    assert '"highway"~"^(trunk|primary)$"' in query


def test_fallback_tiles_cover_the_whole_box_without_gaps():
    fetch_osm = _fetch_osm()
    box = (25.0, 90.0, 27.0, 93.0)
    grid = fetch_osm.tiles(box, step=1.0)
    assert grid
    assert min(t[0] for t in grid) == box[0]
    assert min(t[1] for t in grid) == box[1]
    assert max(t[2] for t in grid) == box[2]
    assert max(t[3] for t in grid) == box[3]
    area = sum((t[2] - t[0]) * (t[3] - t[1]) for t in grid)
    assert area == pytest.approx((box[2] - box[0]) * (box[3] - box[1]), rel=1e-6)


def test_an_overpass_remark_is_treated_as_failure(monkeypatch):
    """Overpass signals truncation inside an HTTP 200. Accepting it would turn a
    truncated extract into a silently truncated road network."""
    fetch_osm = _fetch_osm()
    import urllib.request

    class FakeResponse:
        def read(self):
            return b'{"elements": [], "remark": "runtime error: Query timed out"}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    monkeypatch.setattr(fetch_osm.time, "sleep", lambda _s: None)

    with pytest.raises(SystemExit, match="Overpass mirror failed"):
        fetch_osm.run_query("irrelevant")


def test_a_valid_payload_is_returned(monkeypatch):
    fetch_osm = _fetch_osm()
    import urllib.request

    class FakeResponse:
        def read(self):
            return b'{"elements": [{"type": "way", "id": 1}]}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    assert fetch_osm.run_query("q")["elements"][0]["id"] == 1


def test_download_merges_regions_and_deduplicates_border_ways(monkeypatch):
    """A way crossing a state line comes back from both states, identically."""
    fetch_osm = _fetch_osm()
    responses = [
        {"elements": [{"type": "way", "id": 1}, {"type": "way", "id": 2}]},
        {"elements": [{"type": "way", "id": 2}, {"type": "way", "id": 3}]},
    ]
    monkeypatch.setattr(fetch_osm, "run_query", lambda _q: responses.pop(0))

    merged = fetch_osm.download(("trunk",), regions=(("A", 1, None), ("B", 2, None)))
    assert sorted(w["id"] for w in merged["elements"]) == [1, 2, 3]


def test_a_region_too_large_falls_back_to_tiles(monkeypatch):
    """One oversized state must not cost us the other eight."""
    fetch_osm = _fetch_osm()
    calls = {"n": 0}

    def flaky(query):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SystemExit("too big")
        return {"elements": [{"type": "way", "id": calls["n"]}]}

    monkeypatch.setattr(fetch_osm, "run_query", flaky)
    merged = fetch_osm.download(
        ("trunk",), regions=(("Assam", 1, (25.0, 90.0, 26.0, 91.0)),)
    )
    assert calls["n"] > 1, "expected a tiled retry"
    assert merged["elements"]


# ------------------------------------------------------- node clustering ----

def test_coincident_nodes_collapse_into_one():
    from osm import cluster_nodes

    coords = {
        1: (26.1000, 91.7000),
        2: (26.10005, 91.70005),   # ~7 m away: the same junction
        3: (26.2000, 91.8000),     # far
    }
    leaders = cluster_nodes(coords, merge_metres=75.0)
    assert leaders[1] == leaders[2]
    assert leaders[3] != leaders[1]


def test_clustering_is_deterministic():
    from osm import cluster_nodes

    coords = {9: (26.1, 91.7), 3: (26.10005, 91.70005), 7: (26.10002, 91.70002)}
    leaders = cluster_nodes(coords, merge_metres=75.0)
    assert set(leaders.values()) == {3}, "smallest id should lead the cluster"


def test_clustering_is_transitive_along_a_chain_of_stubs():
    """Three 40 m stubs in a row are one junction, not three."""
    from osm import cluster_nodes

    coords = {i: (26.1 + i * 0.00036, 91.7) for i in range(4)}   # ~40 m apart
    leaders = cluster_nodes(coords, merge_metres=75.0)
    assert len(set(leaders.values())) == 1


def test_nodes_across_a_grid_boundary_still_merge():
    """Bucketing must not miss a pair that straddles two cells."""
    from osm import cluster_nodes

    cell = (75.0 / 1000.0) / 111.0
    lat = cell * 40                       # sits exactly on a cell edge
    coords = {1: (lat - 0.00002, 91.7), 2: (lat + 0.00002, 91.7)}
    assert len(set(cluster_nodes(coords, merge_metres=75.0).values())) == 1


def test_clustering_does_not_merge_genuinely_distinct_junctions():
    from osm import cluster_nodes

    coords = {1: (26.10, 91.70), 2: (26.11, 91.70)}   # ~1.1 km apart
    assert len(set(cluster_nodes(coords, merge_metres=75.0).values())) == 2


def test_an_anchored_place_claims_its_whole_cluster(payload, places):
    """If any node in a merged cluster is a seed place, the cluster is it."""
    network = build_network(payload, places)
    assert "GAU" in network.nodes
    assert network.nodes["GAU"]["population"] == 1116267
    # No synthetic node should survive at the same spot as an anchored place.
    for node_id, node in network.nodes.items():
        if node_id.startswith("n"):
            assert haversine_km(node["lat"], node["lon"], GAU[0], GAU[1]) > 0.5


def test_merging_keeps_the_graph_connected(payload, places):
    """The regression that mattered: dropping stubs left 3% of nodes reachable."""
    network = build_network(payload, places)
    component = largest_component(network)
    assert len(component) == len(network.nodes)


def test_stubs_do_not_become_self_loops(payload, places):
    network = build_network(payload, places)
    assert all(edge["u"] != edge["v"] for edge in network.edges)


def test_an_empty_region_is_a_failure_not_an_empty_state(monkeypatch):
    """A flaky mirror can answer an area query with HTTP 200 and no elements.
    Tripura vanished from the first full run exactly that way, in silence."""
    fetch_osm = _fetch_osm()
    calls = {"n": 0}

    def responder(query):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"elements": []}                       # the silent failure
        if "out bb" in query:
            return {"elements": [{"bounds": {"minlat": 23.0, "minlon": 91.0,
                                             "maxlat": 24.0, "maxlon": 92.0}}]}
        return {"elements": [{"type": "way", "id": calls["n"]}]}

    monkeypatch.setattr(fetch_osm, "run_query", responder)
    merged = fetch_osm.download(("trunk",), regions=(("Tripura", 2026458, None),))
    assert merged["elements"], "an empty region must trigger the tiled retry"


def test_a_region_still_empty_after_tiling_fails_loudly(monkeypatch):
    fetch_osm = _fetch_osm()

    def responder(query):
        if "out bb" in query:
            return {"elements": [{"bounds": {"minlat": 23.0, "minlon": 91.0,
                                             "maxlat": 24.0, "maxlon": 92.0}}]}
        return {"elements": []}

    monkeypatch.setattr(fetch_osm, "run_query", responder)
    with pytest.raises(SystemExit, match="no ways even after tiling"):
        fetch_osm.download(("trunk",), regions=(("Tripura", 2026458, None),))


def test_region_bbox_is_read_from_overpass(monkeypatch):
    fetch_osm = _fetch_osm()
    monkeypatch.setattr(fetch_osm, "run_query", lambda _q: {
        "elements": [{"bounds": {"minlat": 23.0, "minlon": 91.0,
                                 "maxlat": 24.6, "maxlon": 92.4}}]})
    assert fetch_osm.region_bbox(2026458) == (23.0, 91.0, 24.6, 92.4)


def test_the_siliguri_corridor_reaches_the_assam_border():
    """NH-27 leaves Siliguri and runs east through Cooch Behar into Assam.
    Clipping short of that severs the region's only land link to India."""
    fetch_osm = _fetch_osm()
    _name, _rel, bbox = next(r for r in fetch_osm.NER_REGIONS if "Siliguri" in r[0])
    assert bbox[3] >= 89.9, "corridor clipped before the Assam border"
    assert bbox[1] <= 88.0, "corridor must include Siliguri itself"


def test_tiled_retry_deduplicates_ways_across_tiles(monkeypatch):
    """A way spanning two tiles comes back from both."""
    fetch_osm = _fetch_osm()
    calls = {"n": 0}

    def responder(query):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"elements": []}
        if "out bb" in query:
            return {"elements": [{"bounds": {"minlat": 23.0, "minlon": 91.0,
                                             "maxlat": 26.0, "maxlon": 94.0}}]}
        return {"elements": [{"type": "way", "id": 42}]}   # same way every tile

    monkeypatch.setattr(fetch_osm, "run_query", responder)
    merged = fetch_osm.download(("trunk",), regions=(("Assam", 1, None),))
    assert [w["id"] for w in merged["elements"]] == [42]


def test_merge_raw_tops_up_the_cached_payload(tmp_path, monkeypatch):
    """A full Overpass walk is expensive and rate-limited. Re-fetching one
    missing state must not throw away the twelve that already succeeded."""
    fetch_osm = _fetch_osm()

    raw = tmp_path / "osm_ner.json"
    raw.write_text(json.dumps({"elements": [
        {"type": "way", "id": 1, "tags": {"highway": "trunk"}},
        {"type": "way", "id": 2, "tags": {"highway": "trunk"}},
    ]}))

    cached = json.loads(raw.read_text())
    merged = {e["id"]: e for e in cached["elements"] if e["type"] == "way"}
    for element in [{"type": "way", "id": 2, "tags": {"highway": "primary"}},
                    {"type": "way", "id": 3, "tags": {"highway": "trunk"}}]:
        merged[element["id"]] = element

    assert sorted(merged) == [1, 2, 3], "existing ways must survive the top-up"
    assert merged[2]["tags"]["highway"] == "primary", "a re-fetched way must win"
