from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from modelsentry.api import create_app
from modelsentry.model import VictimCNN
from modelsentry.monitor import BenignProfile, StatefulMonitor
from modelsentry.service import PredictionService
from modelsentry.store import EventStore


def test_api_health_and_prediction(tmp_path: Path) -> None:
    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    store = EventStore(tmp_path / "api.db")
    service = PredictionService(
        VictimCNN().eval(),
        StatefulMonitor(BenignProfile(distributions)),
        store,
        defence_enabled=False,
    )
    client = TestClient(create_app(service))

    assert client.get("/health").json() == {"status": "ok"}
    response = client.post(
        "/predict",
        headers={"X-API-Key": "integration-test"},
        json={"pixels": [0.0] * 784},
    )
    store.close()

    assert response.status_code == 200
    assert response.json()["allowed"] is True
    assert response.json()["label"] is not None


def test_api_rejects_missing_key_and_wrong_image_size(tmp_path: Path) -> None:
    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    store = EventStore(tmp_path / "api.db")
    service = PredictionService(
        VictimCNN().eval(),
        StatefulMonitor(BenignProfile(distributions)),
        store,
        defence_enabled=False,
    )
    client = TestClient(create_app(service))

    missing_key = client.post("/predict", json={"pixels": [0.0] * 784})
    wrong_size = client.post(
        "/predict",
        headers={"X-API-Key": "integration-test"},
        json={"pixels": [0.0] * 783},
    )
    store.close()

    assert missing_key.status_code == 422
    assert wrong_size.status_code == 422


def test_api_rejects_out_of_range_pixels(tmp_path: Path) -> None:
    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    store = EventStore(tmp_path / "api.db")
    service = PredictionService(
        VictimCNN().eval(),
        StatefulMonitor(BenignProfile(distributions)),
        store,
        defence_enabled=False,
    )
    client = TestClient(create_app(service))
    pixels = [0.0] * 784
    pixels[10] = 1.5

    response = client.post(
        "/predict",
        headers={"X-API-Key": "integration-test"},
        json={"pixels": pixels},
    )
    store.close()

    assert response.status_code == 422
    assert "within [0, 1]" in response.json()["detail"]
