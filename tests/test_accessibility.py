"""The accessibility index is the policy-facing half of the platform."""
import pytest

from backend.app.services.accessibility import accessibility_index, facility_impact


@pytest.fixture(scope="module")
def july(network, risk_model):
    return accessibility_index(network, risk_model, month="jul")


def test_every_place_is_scored(network, july):
    assert len(july["places"]) == len(network.places)
    assert all(0.0 <= row["accessibility_score"] <= 100.0 for row in july["places"])


def test_places_with_a_market_have_zero_travel_time_to_one(july):
    for row in july["places"]:
        if row["has_market"]:
            assert row["hours_to_market"] == 0


def test_no_place_is_unreachable(july):
    """The seed network is connected, so every score must be computable."""
    for row in july["places"]:
        assert row["hours_to_gateway"] is not None
        assert row["hours_to_market"] is not None


def test_underserved_list_is_the_worst_scoring(july):
    scores = [row["accessibility_score"] for row in july["places"]]
    assert scores == sorted(scores)
    assert [row["id"] for row in july["underserved"]] == [row["id"] for row in july["places"][:10]]


def test_monsoon_degrades_accessibility(network, risk_model):
    dry = {r["id"]: r for r in accessibility_index(network, risk_model, month="jan")["places"]}
    wet = {r["id"]: r for r in accessibility_index(network, risk_model, month="jul")["places"]}
    worse = sum(1 for pid in dry if wet[pid]["accessibility_score"] <= dry[pid]["accessibility_score"])
    assert worse == len(dry), "monsoon must not improve anyone's accessibility"


def test_remote_hill_towns_score_below_the_gateway(july):
    ranked = {row["id"]: row["accessibility_score"] for row in july["places"]}
    for remote in ("TWG", "ZRO", "CHP"):
        assert ranked[remote] < ranked["GAU"]
        assert ranked[remote] < ranked["SLG"]


def test_tiers_are_consistent_with_scores(july):
    for row in july["places"]:
        score, tier = row["accessibility_score"], row["tier"]
        if tier == "well_connected":
            assert score >= 70
        elif tier == "critically_underserved":
            assert score < 30


def test_adding_a_cold_store_never_hurts(network, risk_model):
    before = accessibility_index(network, risk_model, month="jul")
    after = accessibility_index(network, risk_model, month="jul", extra_coldstores={"KHM"})
    before_by_id = {r["id"]: r for r in before["places"]}
    for row in after["places"]:
        assert row["accessibility_score"] >= before_by_id[row["id"]]["accessibility_score"] - 1e-9


def test_facility_impact_ranks_and_reports_population(network, risk_model):
    result = facility_impact(
        network, risk_model, candidate_ids=["KHM", "TWG", "MKG"],
        facility_type="coldstore", threshold_hours=10,
    )
    ranked = result["ranked_sites"]
    assert len(ranked) == 3
    gains = [r["population_newly_covered"] for r in ranked]
    assert gains == sorted(gains, reverse=True)
    for site in ranked:
        assert site["mean_score_after"] >= site["mean_score_before"]


def test_facility_impact_rejects_unknown_site(network, risk_model):
    with pytest.raises(ValueError, match="unknown candidate"):
        facility_impact(network, risk_model, candidate_ids=["NOWHERE"])


def test_facility_impact_rejects_bad_type(network, risk_model):
    with pytest.raises(ValueError, match="facility_type"):
        facility_impact(network, risk_model, candidate_ids=["KHM"], facility_type="airport")
