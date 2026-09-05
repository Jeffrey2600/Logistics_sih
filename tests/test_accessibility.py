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


def test_every_row_is_flagged_as_settlement_or_not(july):
    for row in july["places"]:
        assert isinstance(row["is_settlement"], bool)
        assert isinstance(row["reachable"], bool)


def test_seed_places_are_settlements(july):
    """Every seed place has population, a market or a cold store."""
    assert all(row["is_settlement"] for row in july["places"])
    assert july["settlements"] == len(july["places"])
    assert july["unreachable"] == 0


def test_ranking_excludes_junctions_and_unreachable_nodes(network, risk_model):
    """At OSM scale most nodes are road junctions. Nobody lives at a junction,
    and an unreachable one scores a perfect zero, so ranking every node buries
    the real towns under graph artefacts."""
    from backend.app.core.network import Network, Place

    places = dict(network.places)
    # A junction on the network, and a town cut off from it entirely.
    places["n999"] = Place(id="n999", name="n999", state="", lat=26.0, lon=92.0,
                           kind="junction", population=0,
                           has_market=False, has_coldstore=False)
    places["ORPHAN"] = Place(id="ORPHAN", name="Orphan", state="Assam",
                             lat=27.9, lon=96.9, kind="town", population=5000,
                             has_market=False, has_coldstore=False)
    junction_edge = dict(network.edges[0])
    junction_edge.update({"id": "GAU-n999-road", "u": "GAU", "v": "n999"})

    widened = Network(places=places, edges=network.edges + [junction_edge])
    result = accessibility_index(widened, risk_model, month="jul")

    ranked = {row["id"] for row in result["underserved"]}
    assert "n999" not in ranked, "a road junction is not an underserved place"
    assert "ORPHAN" not in ranked, "an unreachable place cannot be scored"

    # Both still appear in the full list, so the map can draw them.
    all_ids = {row["id"] for row in result["places"]}
    assert {"n999", "ORPHAN"} <= all_ids
    assert result["unreachable"] >= 1


def test_underserved_is_ranked_worst_first_among_settlements(july):
    scores = [row["accessibility_score"] for row in july["underserved"]]
    assert scores == sorted(scores)
    assert all(row["is_settlement"] and row["reachable"] for row in july["underserved"])
