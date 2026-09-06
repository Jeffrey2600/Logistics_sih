"""Segment disruption risk.

Two implementations behind one interface:

* `AnalyticRiskModel` - a transparent susceptibility score built from terrain,
  monsoon exposure, historical landslide density and the seasonal rain index.
  Always available, needs no training data, and every term is explainable.
* `LearnedRiskModel` - loads a gradient-boosted model exported by
  `ml/landslide/train.py` when one is present on disk.

`load_risk_model()` returns the learned model if trained, else the analytic one,
so the API behaves identically whether or not the ML artefact has been built.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Protocol

from ..config import EXPECTED_CLOSURE_HOURS, MODEL_DIR
from .rainfall import rain_index

TERRAIN_BASE = {
    "plain": 0.02,
    "hilly": 0.10,
    "mountain": 0.22,
    "riverine": 0.06,
    "aerial": 0.01,
}

# Modes differ in how a given hazard translates into an outage. A blocked
# carriageway stops trucks outright; a rail landslip is rarer but slower to
# clear; flights are weather-cancelled rather than terrain-blocked.
MODE_SENSITIVITY = {"road": 1.0, "rail": 0.65, "water": 0.5, "air": 0.35}

# `probability` is the chance a segment is disrupted at some point during the
# month - the right number for a risk map and for investment prioritisation.
# A single consignment only occupies a narrow window of that month, so the
# chance *this trip* meets the closure is much lower. Without this conversion
# the optimiser prices every monsoon trip as if it were guaranteed to be caught,
# and every hill route becomes unusable rather than merely expensive.
TRIP_EXPOSURE = 0.20


@dataclass(frozen=True)
class RiskAssessment:
    """Risk of a single segment in a given month."""

    probability: float           # 0-1 chance the segment is disrupted this month
    per_trip_probability: float  # 0-1 chance a single consignment is caught by it
    expected_delay_hours: float  # per-trip probability-weighted closure time
    band: str                    # low | moderate | high | severe
    drivers: dict[str, float]    # per-factor contribution, for explainability

    def to_dict(self) -> dict:
        return {
            "probability": round(self.probability, 4),
            "per_trip_probability": round(self.per_trip_probability, 4),
            "expected_delay_hours": round(self.expected_delay_hours, 2),
            "band": self.band,
            "drivers": {k: round(v, 4) for k, v in self.drivers.items()},
        }


# Three bands, not four. Four warm colours cannot be told apart on a map -
# "high" and "severe" measured a colour-difference of 2.3 for a red-green
# colourblind reader and 8.2 for everyone else, on the two bands that matter
# most. Three bands carry validated, clearly distinct colours, and the risk
# range on the OSM network is compressed enough that a fourth was false
# precision anyway.
def _band(p: float) -> str:
    if p < 0.15:
        return "low"
    if p < 0.35:
        return "elevated"
    return "severe"


class RiskModel(Protocol):
    name: str

    def assess(self, edge: dict, month: str) -> RiskAssessment: ...


class AnalyticRiskModel:
    """Rule-based susceptibility. Deliberately simple and inspectable."""

    name = "analytic-v1"

    def assess(self, edge: dict, month: str) -> RiskAssessment:
        terrain = edge.get("terrain", "plain")
        rain = rain_index(edge, month)

        base = TERRAIN_BASE.get(terrain, 0.05)

        # Historical landslide events normalised per 100 km of segment, then
        # squashed - the tenth recorded slip on a stretch says less than the
        # first, but the stretch is clearly known-bad.
        length = max(float(edge.get("distance_km", 1.0)), 1.0)
        density = float(edge.get("landslide_events", 0)) * 100.0 / length
        history = 1.0 - math.exp(-density / 6.0)

        exposure = float(edge.get("monsoon_exposure", 0.3))

        # Narrow carriageways have no shoulder to push debris onto, so a slip
        # closes the road rather than reducing it to one lane.
        lanes = int(edge.get("lanes", 0) or 0)
        narrow = {1: 0.35, 2: 0.15}.get(lanes, 0.0)

        susceptibility = min(
            1.0, base + 0.45 * history + 0.20 * exposure + narrow * 0.5
        )

        # Rain is the trigger: a susceptible slope is only a hazard when it is
        # loaded with water. Keep a small dry-season floor for washouts and
        # accidents that happen regardless of season.
        probability = susceptibility * (0.15 + 0.85 * rain)
        probability *= MODE_SENSITIVITY.get(edge.get("mode", "road"), 1.0)
        probability = max(0.0, min(1.0, probability))

        closure = EXPECTED_CLOSURE_HOURS.get(terrain, 8.0)
        per_trip = probability * TRIP_EXPOSURE
        return RiskAssessment(
            probability=probability,
            per_trip_probability=per_trip,
            expected_delay_hours=per_trip * closure,
            band=_band(probability),
            drivers={
                "terrain_base": base,
                "landslide_history": history,
                "monsoon_exposure": exposure,
                "narrow_carriageway": narrow,
                "rain_index": rain,
            },
        )


class LearnedRiskModel:
    """Wraps a trained scikit-learn classifier exported to disk."""

    name = "learned-v1"

    def __init__(self, model, feature_order: list[str], fallback: AnalyticRiskModel):
        self._model = model
        self._features = feature_order
        self._fallback = fallback

    def assess(self, edge: dict, month: str) -> RiskAssessment:
        from .features import edge_features  # local import, keeps import cost off the API path

        row = edge_features(edge, month)
        vector = [[row[f] for f in self._features]]
        probability = float(self._model.predict_proba(vector)[0][1])
        probability *= MODE_SENSITIVITY.get(edge.get("mode", "road"), 1.0)

        closure = EXPECTED_CLOSURE_HOURS.get(edge.get("terrain", "plain"), 8.0)
        # Reuse the analytic drivers as the explanation surface - the learned
        # model gives a better number, the analytic terms say why.
        drivers = self._fallback.assess(edge, month).drivers
        per_trip = probability * TRIP_EXPOSURE
        return RiskAssessment(
            probability=probability,
            per_trip_probability=per_trip,
            expected_delay_hours=per_trip * closure,
            band=_band(probability),
            drivers=drivers,
        )


def load_risk_model() -> RiskModel:
    """Learned model when trained, analytic otherwise."""
    analytic = AnalyticRiskModel()
    model_path = MODEL_DIR / "model.joblib"
    meta_path = MODEL_DIR / "model_meta.json"
    if not (model_path.exists() and meta_path.exists()):
        return analytic
    try:
        import joblib

        model = joblib.load(model_path)
        meta = json.loads(meta_path.read_text())
        return LearnedRiskModel(model, meta["feature_order"], analytic)
    except Exception:
        # A broken artefact must never take the API down.
        return analytic
