"""Populated-places ingestion: parsing settlement nodes and joining them to roads."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "ingest"))

from common import haversine_km  # noqa: E402
from places import (  # noqa: E402
    ACCESS_CIRCUITY, attach, nearest_node, parse_places, parse_population,
)

SHILLONG = (25.5788, 91.8933)


def node(osm_id, name, lat, lon, place="village", **tags):
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon,
            "tags": {"place": place, "name": name, **tags}}


# ------------------------------------------------------------- population ---

@pytest.mark.parametrize("raw,expected,known", [
    ("12345", 12345, True),
    ("12,345", 12345, True),
    ("1 200", 1200, True),
    ("approx 5000", 5000, True),
    (None, 0, False),
    ("", 0, False),
    ("unknown", 0, False),
    ("0", 0, False),
    ("99999999999", 0, False),
])
def test_parse_population(raw, expected, known):
    tags = {} if raw is None else {"population": raw}
    assert parse_population(tags) == (expected, known)


def test_unknown_population_is_never_guessed():
    """A fabricated population would flow into the facility-siting ranking and
    quietly decide where a cold store goes."""
    value, known = parse_population({"place": "village", "name": "Somewhere"})
    assert (value, known) == (0, False)


# ----------------------------------------------------------------- parsing --

def test_parses_named_settlements():
    payload = {"elements": [
        node(1, "Nongpoh", 25.9, 91.88, "town", population="12000"),
        node(2, "Umsning", 25.75, 91.88, "village"),
    ]}
    places = parse_places(payload)
    assert [p.name for p in places] == ["Nongpoh", "Umsning"]
    assert places[0].population == 12000 and places[0].population_known
    assert places[1].population == 0 and not places[1].population_known


def test_unnamed_settlements_are_skipped():
    """An unnamed place cannot be reported to anyone, so it is not a finding."""
    payload = {"elements": [{"type": "node", "id": 9, "lat": 25.9, "lon": 91.9,
                             "tags": {"place": "village"}}]}
    assert parse_places(payload) == []


def test_irrelevant_place_classes_are_skipped():
    payload = {"elements": [
        node(1, "A farm", 25.9, 91.9, "isolated_dwelling"),
        node(2, "A county", 25.9, 91.9, "county"),
        node(3, "Real village", 25.9, 91.9, "village"),
    ]}
    assert [p.name for p in parse_places(payload)] == ["Real village"]


def test_ways_and_relations_are_not_settlements():
    payload = {"elements": [{"type": "way", "id": 1, "tags": {"place": "village",
                                                              "name": "Not a node"}}]}
    assert parse_places(payload) == []


def test_name_en_is_accepted_as_a_fallback():
    payload = {"elements": [{"type": "node", "id": 1, "lat": 25.9, "lon": 91.9,
                             "tags": {"place": "town", "name:en": "Shillong"}}]}
    assert parse_places(payload)[0].name == "Shillong"


# ---------------------------------------------------------------- nearest ---

def test_nearest_node_finds_the_closest():
    nodes = {"a": (25.60, 91.90), "b": (25.90, 91.90), "c": (25.5790, 91.8935)}
    cell = 5.0 / 111.0
    from places import _grid_index

    found, km = nearest_node(*SHILLONG, nodes, _grid_index(nodes, cell), cell, 20.0)
    assert found == "c" and km < 0.1


def test_nearest_node_respects_the_radius():
    nodes = {"far": (27.0, 94.0)}
    cell = 5.0 / 111.0
    from places import _grid_index

    found, _ = nearest_node(*SHILLONG, nodes, _grid_index(nodes, cell), cell, 20.0)
    assert found is None


# ----------------------------------------------------------------- attach ---

def make_settlements(payload_nodes):
    return parse_places({"elements": payload_nodes})


def test_settlement_off_the_road_gets_a_connector():
    settlements = make_settlements([node(1, "Village", 25.65, 91.95, population="800")])
    network = {"junction": (25.60, 91.90)}

    nodes, edges, unattached, merged = attach(settlements, network)
    assert not unattached and not merged
    assert nodes[0]["id"] == "s1" and nodes[0]["population"] == 800
    assert edges[0]["u"] == "s1" and edges[0]["v"] == "junction"

    straight = haversine_km(25.65, 91.95, 25.60, 91.90)
    assert edges[0]["distance_km"] == pytest.approx(straight * ACCESS_CIRCUITY, rel=0.01)


def test_last_mile_is_not_measured_as_the_crow_flies():
    """A village 3 km off the highway is not 3 km of driving."""
    settlements = make_settlements([node(1, "Village", 25.65, 91.95)])
    nodes, edges, _u, _m = attach(settlements, {"j": (25.60, 91.90)})
    straight = haversine_km(25.65, 91.95, 25.60, 91.90)
    assert edges[0]["distance_km"] > straight


def test_a_settlement_on_an_existing_node_is_merged_not_duplicated():
    """Otherwise every seed town gains a phantom twin joined by a fictional road."""
    settlements = make_settlements([node(1, "Shillong", *SHILLONG, "city",
                                         population="143229")])
    nodes, edges, unattached, merged = attach(settlements, {"SHL": SHILLONG})
    assert nodes == [] and edges == [] and unattached == []
    assert merged["SHL"].name == "Shillong"


def test_the_best_populated_claimant_wins_a_shared_node():
    settlements = make_settlements([
        node(1, "Hamlet", 25.5789, 91.8934, "hamlet", population="200"),
        node(2, "Shillong", *SHILLONG, "city", population="143229"),
    ])
    _n, _e, _u, merged = attach(settlements, {"SHL": SHILLONG})
    assert merged["SHL"].name == "Shillong"


def test_a_settlement_beyond_the_radius_is_reported_not_dropped():
    settlements = make_settlements([node(1, "Remote", 27.5, 95.5)])
    nodes, edges, unattached, _m = attach(settlements, {"j": (25.6, 91.9)})
    assert nodes == [] and edges == []
    assert [s.name for s in unattached] == ["Remote"]


def test_attaching_to_an_empty_network_reports_everything_unattached():
    settlements = make_settlements([node(1, "Village", 25.65, 91.95)])
    nodes, edges, unattached, merged = attach(settlements, {})
    assert (nodes, edges, merged) == ([], [], {})
    assert len(unattached) == 1


def test_connector_edges_are_single_lane_access_roads():
    settlements = make_settlements([node(1, "Village", 25.65, 91.95)])
    _n, edges, _u, _m = attach(settlements, {"j": (25.60, 91.90)})
    assert edges[0]["lanes"] == 1
    assert edges[0]["route_ref"] == "access"
    assert edges[0]["mode"] == "road"
