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
    assert client.post("/demo/reset").status_code == 404
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


def test_demo_reset_requires_token_and_clears_state(tmp_path: Path) -> None:
    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    profile = BenignProfile(distributions)
    store = EventStore(tmp_path / "api.db")
    service = PredictionService(
        VictimCNN().eval(), StatefulMonitor(profile), store, defence_enabled=True
    )
    client = TestClient(
        create_app(
            service,
            reset_service=lambda: service.reset(StatefulMonitor(profile)),
            demo_reset_token="test-token",
        )
    )
    valid_request = {
        "headers": {"X-API-Key": "integration-test"},
        "json": {"pixels": [0.0] * 784},
    }
    assert client.post("/predict", **valid_request).status_code == 200
    assert client.post("/demo/reset").status_code == 403
    assert (
        client.post(
            "/demo/reset", headers={"X-Demo-Token": "wrong-token"}
        ).status_code
        == 403
    )
    reset = client.post(
        "/demo/reset", headers={"X-Demo-Token": "test-token"}
    )
    assert reset.json() == {"status": "reset"}
    assert store.connection.execute("SELECT COUNT(*) FROM query_events").fetchone()[0] == 0
    assert client.post("/predict", **valid_request).status_code == 200
    first_id = store.connection.execute("SELECT id FROM query_events").fetchone()[0]
    store.close()
    assert first_id == 1


def test_api_survives_malformed_json(tmp_path: Path) -> None:
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
    malformed = client.post(
        "/predict",
        headers={"X-API-Key": "integration-test", "Content-Type": "application/json"},
        content="{",
    )
    valid = client.post(
        "/predict",
        headers={"X-API-Key": "integration-test"},
        json={"pixels": [0.0] * 784},
    )
    count = store.connection.execute("SELECT COUNT(*) FROM query_events").fetchone()[0]
    store.close()

    assert malformed.status_code == 422
    assert valid.status_code == 200
    assert count == 1
