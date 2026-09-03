import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.network import load_network  # noqa: E402
from backend.app.core.risk import AnalyticRiskModel  # noqa: E402


@pytest.fixture(scope="session")
def network():
    return load_network()


@pytest.fixture(scope="session")
def risk_model():
    return AnalyticRiskModel()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)
