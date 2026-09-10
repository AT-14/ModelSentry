from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
import torch

from modelsentry.model import VictimCNN
from modelsentry.monitor import BenignProfile, StatefulMonitor
from modelsentry.service import PredictionService
from modelsentry.store import EventStore


def make_service(database: Path) -> tuple[PredictionService, EventStore]:
    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    store = EventStore(database)
    service = PredictionService(
        VictimCNN().eval(),
        StatefulMonitor(BenignProfile(distributions)),
        store,
        defence_enabled=False,
    )
    return service, store


def test_service_predicts_and_logs(tmp_path: Path) -> None:
    service, store = make_service(tmp_path / "events.db")
    response = service.predict("test-key", torch.zeros(1, 28, 28), 1.0)
    count = store.connection.execute("SELECT COUNT(*) FROM query_events").fetchone()[0]
    store.close()
    assert response.allowed
    assert response.label is not None
    assert count == 1


def test_service_rejects_invalid_image(tmp_path: Path) -> None:
    service, store = make_service(tmp_path / "events.db")
    with pytest.raises(ValueError, match="shape"):
        service.predict("test-key", torch.zeros(28, 28), 1.0)
    store.close()


def test_service_rejects_invalid_identity_and_values(tmp_path: Path) -> None:
    service, store = make_service(tmp_path / "events.db")
    with pytest.raises(ValueError, match="must not be empty"):
        service.predict(" ", torch.zeros(1, 28, 28), 1.0)
    with pytest.raises(ValueError, match="within"):
        service.predict("test-key", torch.full((1, 28, 28), 2.0), 1.0)
    with pytest.raises(ValueError, match="finite"):
        image = torch.zeros(1, 28, 28)
        image[0, 0, 0] = float("nan")
        service.predict("test-key", image, 1.0)
    store.close()


def test_service_reset_clears_enforcement_and_event_ids(tmp_path: Path) -> None:
    service, store = make_service(tmp_path / "events.db")
    service.predict("test-key", torch.zeros(1, 28, 28), 1.0)

    distributions = {
        name: np.linspace(0, 10, 20)
        for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
    }
    service.reset(StatefulMonitor(BenignProfile(distributions)))
    response = service.predict("test-key", torch.ones(1, 28, 28), 2.0)
    rows = store.connection.execute(
        "SELECT id, action FROM query_events ORDER BY id"
    ).fetchall()
    store.close()

    assert response.allowed
    assert rows == [(1, "allow")]


def test_service_serializes_concurrent_predictions(tmp_path: Path) -> None:
    service, store = make_service(tmp_path / "events.db")

    def send(index: int):
        return service.predict(
            f"client-{index % 3}", torch.full((1, 28, 28), index / 20), float(index)
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(send, range(12)))
    count = store.connection.execute("SELECT COUNT(*) FROM query_events").fetchone()[0]
    store.close()

    assert all(response.allowed for response in responses)
    assert count == 12
