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


# ------------------------------------------------------------ graph cache ---

def test_cached_graph_returns_the_same_object(network, risk_model):
    from backend.app.core.network import cached_graph, clear_graph_cache

    clear_graph_cache()
    weights = {"cost": 0.4, "time": 0.4, "risk": 0.2}
    first = cached_graph(network, risk_model, "jul", weights)
    second = cached_graph(network, risk_model, "jul", weights)
    assert first is second


def test_cache_key_separates_what_changes_the_graph(network, risk_model):
    from backend.app.core.network import cached_graph, clear_graph_cache

    clear_graph_cache()
    base = {"cost": 0.4, "time": 0.4, "risk": 0.2}
    graph = cached_graph(network, risk_model, "jul", base)
    assert cached_graph(network, risk_model, "jan", base) is not graph
    assert cached_graph(network, risk_model, "jul", {"cost": 1, "time": 0, "risk": 0}) is not graph
    assert cached_graph(network, risk_model, "jul", base, allowed_modes={"road"}) is not graph
    assert cached_graph(network, risk_model, "jul", base,
                        blocked_edge_ids={"SLG-GTK-road"}) is not graph
    assert cached_graph(network, risk_model, "jul", base, value_of_time=900) is not graph


def test_terminals_are_removed_so_a_cached_graph_is_not_corrupted(network, risk_model):
    """Planning mutates the graph to add a super-source and sink. Leaving them
    behind would poison every later request that hits the same cache entry."""
    from backend.app.core.network import cached_graph, clear_graph_cache
    from backend.app.services.routing import plan_route

    clear_graph_cache()
    weights = {"cost": 0.4, "time": 0.4, "risk": 0.2}
    graph = cached_graph(network, risk_model, "jul", weights)
    before = graph.number_of_nodes()

    plan_route(network, risk_model, "KHM", "GAU", month="jul")
    assert graph.number_of_nodes() == before
    assert not graph.has_node(("__src__", "*"))
    assert not graph.has_node(("__dst__", "*"))


def test_repeated_plans_stay_identical_with_a_warm_cache(network, risk_model):
    """A stale terminal would silently change the second answer."""
    from backend.app.core.network import clear_graph_cache
    from backend.app.services.routing import plan_route

    clear_graph_cache()
    first = plan_route(network, risk_model, "IMP", "GAU", month="jul")
    second = plan_route(network, risk_model, "IMP", "GAU", month="jul")
    assert first["recommended"]["summary"] == second["recommended"]["summary"]


def test_a_failed_plan_still_cleans_up_its_terminals(network, risk_model):
    from backend.app.core.network import cached_graph, clear_graph_cache
    from backend.app.services.routing import RoutingError, plan_route

    clear_graph_cache()
    weights = {"cost": 0.4, "time": 0.4, "risk": 0.2}
    graph = cached_graph(network, risk_model, "jul", weights,
                         blocked_edge_ids={"SLG-GTK-road"})
    before = graph.number_of_nodes()
    try:
        plan_route(network, risk_model, "GTK", "GAU", month="jul",
                   blocked_edge_ids=["SLG-GTK-road"])
    except RoutingError:
        pass
    assert graph.number_of_nodes() == before


def test_modes_by_place_is_built_in_one_pass(network):
    """Scanning every edge per place is quadratic; at OSM scale that was 119
    million comparisons and about fifteen seconds of graph build."""
    modes = network.modes_by_place()
    for edge in network.edges:
        assert edge["mode"] in modes[edge["u"]]
        assert edge["mode"] in modes[edge["v"]]
    assert network.modes_at("GAU") == modes["GAU"]
    assert network.modes_at("NOWHERE") == set()


def test_modes_index_notices_appended_edges(network):
    """Tests and merges append edges after construction; a cache keyed on the
    instance alone would keep serving the pre-merge answer."""
    from backend.app.core.network import Network

    net = Network(places=dict(network.places), edges=list(network.edges))
    assert "water" not in net.modes_at("KHM")
    net.edges.append({
        "id": "KHM-GAU-water", "u": "KHM", "v": "GAU", "mode": "water",
        "distance_km": 10.0, "terrain": "riverine", "route_ref": "NW-X",
        "lanes": 0, "monsoon_exposure": 0.5, "landslide_events": 0,
    })
    assert "water" in net.modes_at("KHM")


def test_graph_build_is_not_quadratic_in_places():
    """A star network: one hub, many leaves. Build time must track edges, not
    places times edges."""
    import time

    from backend.app.core.network import Network, Place, build_graph
    from backend.app.core.risk import AnalyticRiskModel

    def build(n):
        places = {"HUB": Place(id="HUB", name="HUB", state="", lat=26.0, lon=92.0,
                               kind="city", population=1, has_market=True,
                               has_coldstore=True)}
        edges = []
        for i in range(n):
            pid = f"p{i}"
            places[pid] = Place(id=pid, name=pid, state="", lat=26.0 + i * 1e-4,
                                lon=92.0, kind="village", population=0,
                                has_market=False, has_coldstore=False)
            edges.append({"id": f"HUB-{pid}-road", "u": "HUB", "v": pid,
                          "mode": "road", "distance_km": 5.0, "terrain": "plain",
                          "route_ref": "NH", "lanes": 2,
                          "monsoon_exposure": 0.3, "landslide_events": 0})
        net = Network(places=places, edges=edges)
        weights = {"cost": 0.4, "time": 0.4, "risk": 0.2}
        start = time.perf_counter()
        build_graph(net, AnalyticRiskModel(), "jul", weights)
        return time.perf_counter() - start

    small, large = build(200), build(1600)
    # Eight times the size. Quadratic would be ~64x; allow generous headroom
    # for timing noise while still failing a return to O(places x edges).
    assert large < small * 25, f"build scaled {large / max(small, 1e-6):.0f}x for 8x the network"
