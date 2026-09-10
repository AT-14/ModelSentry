from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from modelsentry.api import create_app
from modelsentry.live import read_live_state
from modelsentry.model import VictimCNN
from modelsentry.monitor import BenignProfile
from modelsentry.service import PredictionService
from modelsentry.store import EventStore
from modelsentry.validation_v2 import EnhancedMonitor


def test_live_normal_to_attack_flow_repeats_cleanly(tmp_path: Path) -> None:
    distributions = {
        "rate": np.array([1.0, 20.0]),
        "diversity": np.array([0.0, 1000.0]),
        "boundary": np.array([0.0, 1000.0]),
        "class_coverage": np.array([0.0, 1000.0]),
        "acquisition": np.array([0.0, 1000.0]),
    }
    profile = BenignProfile(distributions)
    database = tmp_path / "live.db"
    store = EventStore(database)
    service = PredictionService(
        VictimCNN().eval(), EnhancedMonitor(profile), store, defence_enabled=True
    )
    client = TestClient(
        create_app(
            service,
            reset_service=lambda: service.reset(EnhancedMonitor(profile)),
            demo_reset_token="test-token",
        )
    )
    generator = np.random.default_rng(42)
    normal_images = generator.random((60, 784), dtype=np.float32).tolist()
    attack_pool = generator.random((50, 784), dtype=np.float32).tolist()

    for run in range(2):
        reset = client.post(
            "/demo/reset", headers={"X-Demo-Token": "test-token"}
        )
        assert reset.status_code == 200
        for pixels in normal_images:
            response = client.post(
                "/predict",
                headers={"X-API-Key": "normal-client"},
                json={"pixels": pixels},
            )
            assert response.status_code == 200
            assert response.json()["action"] not in {"throttle", "block"}

        alert = None
        for query in range(1, 151):
            response = client.post(
                "/predict",
                headers={"X-API-Key": "extractor-client"},
                json={"pixels": attack_pool[(query - 1) % len(attack_pool)]},
            )
            assert response.status_code == 200
            if response.json()["action"] in {"throttle", "block"}:
                alert = (query, response.json())
                break

        assert alert is not None
        assert alert[0] == 102
        assert any("repeated-query ratio" in reason for reason in alert[1]["reasons"])
        state = read_live_state(database)
        assert state["phase"] == "alert"
        assert state["normal_requests"] == 60
        assert state["attack_requests"] == 102
        assert state["alert"]["attack_query"] == 102
        assert state["recent_events"]
        first_id = store.connection.execute(
            "SELECT MIN(id) FROM query_events"
        ).fetchone()[0]
        assert first_id == 1, f"event IDs did not reset on run {run + 1}"

    store.close()


def test_live_state_tolerates_invalid_json_fields(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    store = EventStore(database)
    with store.connection:
        store.connection.execute(
            """
            INSERT INTO query_events (
                timestamp, client_id, predicted_class, confidence, risk,
                action, allowed, signals_json, reasons_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1.0, "normal-client", 0, 0.5, 0.0, "allow", 1, "not-json", "{}"),
        )
    state = read_live_state(database)
    store.close()

    assert state["phase"] == "normal"
    assert state["latest"]["signals"] == {}
    assert state["latest"]["reasons"] == []


def test_live_state_handles_non_extractor_alert(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    store = EventStore(database)
    with store.connection:
        store.connection.execute(
            """
            INSERT INTO query_events (
                timestamp, client_id, predicted_class, confidence, risk,
                action, allowed, signals_json, reasons_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1.0, "other-client", 0, 0.5, 0.9, "throttle", 0, "{}", "[]"),
        )
    state = read_live_state(database)
    store.close()

    assert state["phase"] == "alert"
    assert state["alert"]["client_id"] == "other-client"
    assert "attack_query" not in state["alert"]
