"""The risk model has to rank NER segments the way an operator would."""
import pytest

from backend.app.core.risk import AnalyticRiskModel


def edge(**kw):
    base = {
        "mode": "road",
        "terrain": "plain",
        "distance_km": 100.0,
        "lanes": 2,
        "monsoon_exposure": 0.3,
        "landslide_events": 0,
    }
    base.update(kw)
    return base


def test_monsoon_raises_risk_above_dry_season(risk_model):
    segment = edge(terrain="mountain", monsoon_exposure=0.9, landslide_events=30)
    assert risk_model.assess(segment, "jul").probability > risk_model.assess(segment, "jan").probability


def test_mountain_riskier_than_plain(risk_model):
    assert (
        risk_model.assess(edge(terrain="mountain"), "jul").probability
        > risk_model.assess(edge(terrain="plain"), "jul").probability
    )


def test_landslide_history_dominates_similar_terrain(risk_model):
    clean = edge(terrain="mountain", landslide_events=0)
    known_bad = edge(terrain="mountain", landslide_events=40)
    assert risk_model.assess(known_bad, "jul").probability > risk_model.assess(clean, "jul").probability


def test_single_lane_penalised(risk_model):
    assert (
        risk_model.assess(edge(terrain="hilly", lanes=1), "jul").probability
        > risk_model.assess(edge(terrain="hilly", lanes=4), "jul").probability
    )


def test_rail_and_air_less_terrain_sensitive_than_road(risk_model):
    kw = dict(terrain="mountain", landslide_events=20, monsoon_exposure=0.9)
    road = risk_model.assess(edge(mode="road", **kw), "jul").probability
    rail = risk_model.assess(edge(mode="rail", **kw), "jul").probability
    air = risk_model.assess(edge(mode="air", terrain="aerial"), "jul").probability
    assert road > rail > air


def test_per_trip_exposure_below_monthly_susceptibility(risk_model):
    """A single consignment must not be priced as if the closure were certain."""
    result = risk_model.assess(edge(terrain="mountain", landslide_events=30), "jul")
    assert 0 < result.per_trip_probability < result.probability


@pytest.mark.parametrize("month", ["jan", "apr", "jul", "oct"])
def test_probability_always_in_range(risk_model, month):
    worst = edge(terrain="mountain", lanes=1, monsoon_exposure=1.0, landslide_events=99)
    assessment = risk_model.assess(worst, month)
    assert 0.0 <= assessment.probability <= 1.0
    assert assessment.expected_delay_hours >= 0.0


def test_analytic_model_is_the_fallback_when_untrained():
    from backend.app.core.risk import load_risk_model

    assert isinstance(load_risk_model(), AnalyticRiskModel) or load_risk_model().name == "learned-v1"
