"""Seed data integrity and graph construction."""
from backend.app.config import MODES
from backend.app.core.network import build_graph, haversine_km


def test_seed_network_loads(network):
    assert len(network.places) >= 40
    assert len(network.edges) >= 70


def test_every_edge_references_known_places(network):
    for edge in network.edges:
        assert edge["u"] in network.places
        assert edge["v"] in network.places
        assert edge["mode"] in MODES


def test_stated_distances_are_at_least_great_circle(network):
    """Guards against typos: nothing travels shorter than the straight line."""
    for edge in network.edges:
        straight = haversine_km(network.places[edge["u"]], network.places[edge["v"]])
        # Flights are near-direct; surface modes must be at least the chord.
        floor = straight * 0.98 if edge["mode"] == "air" else straight
        assert edge["distance_km"] >= floor, (
            f"{edge['id']}: stated {edge['distance_km']}km < great circle {straight:.1f}km"
        )


def test_surface_routes_are_plausibly_circuitous(network):
    """Hill roads wander; a stated length far above the chord is a data smell."""
    for edge in network.edges:
        if edge["mode"] in ("air", "water"):
            continue
        straight = haversine_km(network.places[edge["u"]], network.places[edge["v"]])
        assert edge["distance_km"] <= straight * 3.0, f"{edge['id']} implausibly long"


def test_network_is_connected_by_road(network):
    """Every place must be reachable, or the accessibility index is meaningless."""
    import networkx as nx

    graph = nx.Graph()
    for edge in network.edges:
        graph.add_edge(edge["u"], edge["v"])
    assert nx.is_connected(graph)
    assert set(graph.nodes) == set(network.places)


def test_transfer_edges_created_at_multimodal_nodes(network, risk_model):
    graph = build_graph(network, risk_model, "jul", {"cost": 0.4, "time": 0.4, "risk": 0.2})
    transfers = [d for _, _, d in graph.edges(data=True) if d["kind"] == "transfer"]
    assert transfers, "expected transfer edges at multimodal places"
    # Guwahati is served by road, rail and air; its river port is Pandu.
    assert graph.has_edge(("GAU", "road"), ("GAU", "rail"))
    assert graph.has_edge(("GAU", "air"), ("GAU", "road"))
    assert graph.has_edge(("PDU", "water"), ("PDU", "road"))


def test_transfers_are_never_free(network, risk_model):
    graph = build_graph(network, risk_model, "jul", {"cost": 0.4, "time": 0.4, "risk": 0.2})
    for _, _, data in graph.edges(data=True):
        if data["kind"] == "transfer":
            assert data["cost"].hours > 0
            assert data["cost"].cost_per_tonne > 0


def test_mode_filter_excludes_other_layers(network, risk_model):
    graph = build_graph(
        network, risk_model, "jul", {"cost": 1, "time": 0, "risk": 0}, allowed_modes={"road"}
    )
    assert all(node[1] == "road" for node in graph.nodes)
