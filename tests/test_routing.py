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


# ------------------------------------------------------ option comparison ---

def test_compare_returns_every_scenario(network, risk_model):
    from backend.app.services.routing import SCENARIOS, compare_options

    result = compare_options(network, risk_model, "KHM", "GAU", month="jul")
    assert len(result["options"]) == len(SCENARIOS)
    assert all("label" in o for o in result["options"])


def test_compare_marks_the_balanced_plan_as_overall_best(network, risk_model):
    """Each scenario minimises a different objective, so their scores are not
    on one scale; picking the smallest named whichever weighting happened to
    produce small numbers."""
    from backend.app.services.routing import compare_options

    result = compare_options(network, risk_model, "KHM", "GAU", month="jul")
    assert result["best"]["overall"] == "recommended"


def test_compare_superlatives_match_the_numbers(network, risk_model):
    from backend.app.services.routing import compare_options

    result = compare_options(network, risk_model, "IMP", "GAU", month="jul")
    usable = [o for o in result["options"] if o["available"]]
    by_key = {o["key"]: o for o in usable}

    assert by_key[result["best"]["cheapest"]]["cost_per_tonne"] == min(
        o["cost_per_tonne"] for o in usable)
    assert by_key[result["best"]["fastest"]]["total_hours"] == min(
        o["total_hours"] for o in usable)
    assert by_key[result["best"]["most_reliable"]]["expected_delay_hours"] == min(
        o["expected_delay_hours"] for o in usable)


def test_compare_reports_an_impossible_scenario_rather_than_hiding_it(network, risk_model):
    """'There is no rail on this lane' is a finding, not a blank row."""
    from backend.app.services.routing import compare_options

    result = compare_options(network, risk_model, "TWG", "GAU", month="jul")
    for option in result["options"]:
        assert option["available"] or option["reason"]


def test_compare_counts_distinct_plans(network, risk_model):
    """Several scenarios often produce the same journey; the view should say
    how many genuinely different options exist."""
    from backend.app.services.routing import compare_options

    result = compare_options(network, risk_model, "KHM", "GAU", month="jul")
    assert 1 <= result["distinct_plans"] <= len(result["options"])


def test_compare_rejects_an_unknown_place(network, risk_model):
    from backend.app.services.routing import RoutingError, compare_options

    with pytest.raises(RoutingError):
        compare_options(network, risk_model, "ZZZ", "GAU")
