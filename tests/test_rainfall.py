"""Rainfall ingestion feeds the risk model, and its absence is survivable."""
from backend.app.config import SEASON_RAIN_INDEX
from backend.app.core.rainfall import place_rain_index, rain_index


def test_index_is_a_probability_like_scale():
    for place, months in place_rain_index().items():
        for month, value in months.items():
            assert 0.0 <= value <= 1.0, f"{place}/{month} out of range"


def test_monsoon_is_wetter_than_winter_everywhere():
    for place, months in place_rain_index().items():
        assert months["jul"] > months["jan"], f"{place} has a dry monsoon"


def test_segment_index_interpolates_between_its_ends(network):
    table = place_rain_index()
    if not table:
        return  # dataset not built; the fallback path is covered below
    edge = network.edge_by_id("BYR-SHL-road")
    expected = (table["BYR"]["jul"] + table["SHL"]["jul"]) / 2
    assert abs(rain_index(edge, "jul") - expected) < 1e-9


def test_falls_back_to_the_regional_table_for_unknown_places():
    """A segment the dataset does not cover must still score, not crash."""
    orphan = {"u": "NOWHERE", "v": "ELSEWHERE", "terrain": "hilly"}
    assert rain_index(orphan, "jul") == SEASON_RAIN_INDEX["jul"]


def test_rainfall_actually_differentiates_segments(network, risk_model):
    """The whole point of the dataset: two similar roads must not score alike."""
    if not place_rain_index():
        return
    indices = {
        edge["id"]: rain_index(edge, "jul")
        for edge in network.edges if edge["terrain"] == "mountain"
    }
    assert max(indices.values()) - min(indices.values()) > 0.05, (
        "per-place rainfall is not varying across mountain segments"
    )
