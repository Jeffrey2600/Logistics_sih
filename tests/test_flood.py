"""Flood is a separate hazard from landslides, and strikes opposite ground."""
import pytest

from backend.app.core import flood
from backend.app.core.risk import AnalyticRiskModel, combine


@pytest.fixture(autouse=True)
def elevation(monkeypatch):
    """A valley road, a hill road and one with no elevation data."""
    monkeypatch.setattr(flood, "_elevation", {
        "VALLEY_A": 55.0, "VALLEY_B": 62.0,     # Brahmaputra floodplain
        "MID_A": 250.0, "MID_B": 260.0,
        "HILL_A": 1400.0, "HILL_B": 1500.0,
    })


def edge(u, v, terrain="plain", mode="road", **kw):
    base = {"u": u, "v": v, "mode": mode, "terrain": terrain, "distance_km": 40.0,
            "lanes": 2, "monsoon_exposure": 0.5, "landslide_events": 0}
    base.update(kw)
    return base


# ---------------------------------------------------------------- elevation --

def test_segment_takes_the_lower_of_its_two_ends():
    """A road floods at its lowest point, not its average."""
    assert flood.segment_elevation(edge("VALLEY_A", "MID_A")) == 55.0


def test_missing_elevation_is_none_not_zero():
    """Zero would read as sea level and flag every unknown road as floodplain."""
    assert flood.segment_elevation(edge("NOWHERE", "ELSEWHERE")) is None


@pytest.mark.parametrize("metres,expected", [
    (10.0, 1.0), (90.0, 1.0), (400.0, 0.0), (1200.0, 0.0), (None, 0.0),
])
def test_lowland_score(metres, expected):
    assert flood.lowland_score(metres) == pytest.approx(expected)


def test_lowland_score_tapers_between_floodplain_and_upland():
    mid = flood.lowland_score(245.0)
    assert 0.0 < mid < 1.0


# -------------------------------------------------------------------- risk --

def test_valley_floods_and_hills_do_not():
    valley = flood.assess(edge("VALLEY_A", "VALLEY_B"), "jul", 1.0)
    hill = flood.assess(edge("HILL_A", "HILL_B", terrain="mountain"), "jul", 1.0)
    assert valley.probability > 0.05
    assert hill.probability == pytest.approx(0.0)


def test_flooding_is_seasonal():
    segment = edge("VALLEY_A", "VALLEY_B")
    assert (flood.assess(segment, "jul", 1.0).probability
            > flood.assess(segment, "jan", 1.0).probability)


def test_a_flat_upland_plateau_does_not_flood():
    """Flatness alone is not enough - the water has to come from somewhere."""
    assert flood.assess(edge("HILL_A", "HILL_B", terrain="plain"), "jul", 1.0
                        ).probability == pytest.approx(0.0)


def test_a_low_gorge_floods_less_than_a_low_plain():
    plain = flood.assess(edge("VALLEY_A", "VALLEY_B", terrain="plain"), "jul", 1.0)
    gorge = flood.assess(edge("VALLEY_A", "VALLEY_B", terrain="mountain"), "jul", 1.0)
    assert plain.probability > gorge.probability


def test_barges_and_aircraft_are_not_stopped_by_high_water():
    kw = dict(terrain="plain")
    road = flood.assess(edge("VALLEY_A", "VALLEY_B", **kw), "jul", 1.0).probability
    barge = flood.assess(edge("VALLEY_A", "VALLEY_B", mode="water", **kw), "jul", 1.0).probability
    plane = flood.assess(edge("VALLEY_A", "VALLEY_B", mode="air", **kw), "jul", 1.0).probability
    assert road > barge > plane


def test_probability_stays_in_range():
    for month in ("jan", "jul", "oct"):
        for rain in (0.0, 0.5, 1.0):
            p = flood.assess(edge("VALLEY_A", "VALLEY_B"), month, rain).probability
            assert 0.0 <= p <= 1.0


def test_a_flooded_road_is_shut_longer_than_a_cleared_landslip():
    assert flood.FLOOD_CLOSURE_HOURS > 24


# --------------------------------------------------------------- combining --

def test_hazards_combine_as_independent_not_additive():
    """Two 60% hazards are not 120%."""
    assert combine(0.6, 0.6) == pytest.approx(0.84)
    assert combine(0.0, 0.0) == 0.0
    assert combine(1.0, 0.5) == 1.0


def test_combined_risk_is_at_least_either_hazard():
    for a in (0.0, 0.3, 0.9):
        for b in (0.0, 0.4, 0.7):
            assert combine(a, b) >= max(a, b) - 1e-9


def test_the_dominant_hazard_is_reported():
    model = AnalyticRiskModel()
    valley = model.assess(edge("VALLEY_A", "VALLEY_B", terrain="plain",
                               monsoon_exposure=0.2), "jul")
    hill = model.assess(edge("HILL_A", "HILL_B", terrain="mountain",
                             landslide_events=40, monsoon_exposure=0.9), "jul")
    assert valley.dominant == "flood"
    assert hill.dominant == "landslide"


def test_flood_and_landslide_are_reported_separately():
    """One number would let a hill road's landslide risk stand in for a valley
    road's flood risk, and both would be wrong."""
    payload = AnalyticRiskModel().assess(edge("VALLEY_A", "VALLEY_B"), "jul").to_dict()
    assert {"landslide", "flood", "dominant"} <= set(payload)
    assert payload["probability"] >= max(payload["landslide"], payload["flood"]) - 1e-9


def test_without_elevation_data_flood_risk_is_zero_not_guessed(monkeypatch):
    """A missing dataset must degrade to 'we do not know', never to a number."""
    monkeypatch.setattr(flood, "_elevation", {})
    assert not flood.data_available()
    assert flood.assess(edge("VALLEY_A", "VALLEY_B"), "jul", 1.0).probability == 0.0


def test_coverage_reports_the_measured_share(monkeypatch):
    """A half-built elevation dataset would paint the unmeasured half of the
    valley green, because no elevation scores zero flood risk."""
    monkeypatch.setattr(flood, "_elevation", {"a": 50.0, "b": 60.0})
    assert flood.coverage(["a", "b", "c", "d"]) == pytest.approx(0.5)
    assert flood.coverage(["a", "b"]) == pytest.approx(1.0)
    assert flood.coverage([]) == 0.0
    assert flood.coverage(["x", "y"]) == 0.0


def test_coverage_is_zero_without_the_dataset(monkeypatch):
    monkeypatch.setattr(flood, "_elevation", {})
    assert flood.coverage(["a", "b"]) == 0.0
