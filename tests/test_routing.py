"""Routing must make the trade-offs an NER freight planner would recognise."""
import pytest

from backend.app.services.routing import RoutingError, plan_route, seasonal_comparison


def plan(network, risk_model, origin, destination, **kw):
    return plan_route(network, risk_model, origin, destination, **kw)


def test_returns_connected_itinerary(network, risk_model):
    result = plan(network, risk_model, "KHM", "GAU", month="jul")
    legs = [leg for leg in result["recommended"]["legs"] if leg["type"] == "travel"]
    assert legs[0]["from"] == "KHM"
    assert legs[-1]["to"] == "GAU"
    for a, b in zip(legs, legs[1:]):
        assert a["to"] == b["from"], "itinerary has a gap"


def test_monsoon_costs_more_time_than_dry_season(network, risk_model):
    """Surface freight only. With air allowed the model may answer a bad
    monsoon by flying, which is correct behaviour but not what this asserts."""
    surface = ["road", "rail", "water"]
    dry = plan(network, risk_model, "AZL", "GAU", month="jan", modes=surface)["recommended"]["summary"]
    wet = plan(network, risk_model, "AZL", "GAU", month="jul", modes=surface)["recommended"]["summary"]
    assert wet["total_hours"] > dry["total_hours"]


def test_seasonal_comparison_reports_a_delta(network, risk_model):
    result = seasonal_comparison(network, risk_model, "AZL", "GAU", alternatives=0,
                                 modes=["road", "rail", "water"])
    assert result["delta"]["hours"] > 0
    assert result["dry_season"]["month"] == "jan"
    assert result["monsoon"]["month"] == "jul"


def test_cost_weighting_never_beats_air_on_price(network, risk_model):
    """Cost-minimising freight must not fly."""
    result = plan(
        network, risk_model, "AZL", "GAU", month="jul",
        weights={"cost": 1.0, "time": 0.0, "risk": 0.0},
    )
    assert "air" not in result["recommended"]["summary"]["mode_chain"]


def test_high_value_of_time_can_justify_air(network, risk_model):
    """Perishables with a punishing spoilage cost should be allowed to fly."""
    result = plan(network, risk_model, "AZL", "GAU", month="jul", value_of_time=5000)
    assert "air" in result["recommended"]["summary"]["mode_chain"]


def test_mode_restriction_is_respected(network, risk_model):
    result = plan(network, risk_model, "IMP", "GAU", modes=["road"])
    assert set(result["recommended"]["summary"]["mode_chain"]) == {"road"}


def test_closure_forces_a_different_route(network, risk_model):
    """Barak Valley reaches Guwahati through the Haflong hill section.

    Both the road and the rail alignment thread the same gorge. Closing the
    one the optimiser picked must push it onto the other, at a worse score -
    that is the whole Silchar connectivity problem in one assertion.
    """
    open_route = plan(network, risk_model, "SCR", "GAU", month="jul")
    used = [leg["edge_id"] for leg in open_route["recommended"]["legs"] if leg["type"] == "travel"]
    assert any("HFL" in edge_id for edge_id in used), "expected the Haflong corridor"

    closed = plan(
        network, risk_model, "SCR", "GAU", month="jul",
        blocked_edge_ids=[e for e in used if "HFL" in e],
    )
    rerouted = {leg.get("edge_id") for leg in closed["recommended"]["legs"]}
    assert not rerouted & set(used)
    # The fallback need not be slower - it may be a faster road at higher cost
    # and risk - but it must be worse on the objective actually minimised.
    assert (
        closed["recommended"]["summary"]["objective_score"]
        > open_route["recommended"]["summary"]["objective_score"]
    )


def test_isolating_a_place_reports_it_as_isolated(network, risk_model):
    """NH-10 is Sikkim's only road link; closing it must say so, not 500."""
    with pytest.raises(RoutingError, match="isolated"):
        plan(network, risk_model, "GTK", "GAU", blocked_edge_ids=["SLG-GTK-road"])


def test_transhipments_are_counted(network, risk_model):
    result = plan(network, risk_model, "KHM", "GAU", month="jul")
    summary = result["recommended"]["summary"]
    assert summary["transhipments"] == max(0, len(summary["mode_chain"]) - 1)


def test_alternatives_are_distinct(network, risk_model):
    result = plan(network, risk_model, "IMP", "GAU", alternatives=3)
    signatures = [
        tuple(leg.get("edge_id") for leg in itinerary["legs"])
        for itinerary in [result["recommended"], *result["alternatives"]]
    ]
    assert len(signatures) == len(set(signatures))


def test_recommended_is_the_best_by_generalised_cost(network, risk_model):
    result = plan(network, risk_model, "IMP", "GAU", alternatives=3)
    # Yen's algorithm yields paths in non-decreasing order of the objective;
    # the recommendation must be the first of them.
    best = result["recommended"]["summary"]
    for alt in result["alternatives"]:
        assert best["objective_score"] <= alt["summary"]["objective_score"]


@pytest.mark.parametrize("origin,destination", [("XXX", "GAU"), ("GAU", "XXX")])
def test_unknown_place_rejected(network, risk_model, origin, destination):
    with pytest.raises(RoutingError, match="unknown"):
        plan(network, risk_model, origin, destination)


def test_same_origin_and_destination_rejected(network, risk_model):
    with pytest.raises(RoutingError, match="same place"):
        plan(network, risk_model, "GAU", "GAU")


def test_unknown_mode_rejected(network, risk_model):
    with pytest.raises(RoutingError, match="unknown mode"):
        plan(network, risk_model, "IMP", "GAU", modes=["teleport"])
