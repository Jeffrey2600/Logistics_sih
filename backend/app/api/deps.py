"""Shared, process-lifetime resources."""
from __future__ import annotations

from functools import lru_cache

from ..core.network import Network, load_network
from ..core.risk import RiskModel, load_risk_model


@lru_cache(maxsize=1)
def get_risk_model() -> RiskModel:
    return load_risk_model()


def get_network() -> Network:
    return load_network()
