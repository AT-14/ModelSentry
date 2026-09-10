import hashlib
import threading
from dataclasses import dataclass, replace

import numpy as np
import torch

from .model import VictimCNN, predict_batch
from .monitor import Monitor, QueryRecord, RiskAssessment
from .store import EventStore


@dataclass(frozen=True)
class PredictionResponse:
    allowed: bool
    label: int | None
    probabilities: np.ndarray | None
    assessment: RiskAssessment


class PredictionService:
    def __init__(
        self,
        model: VictimCNN,
        monitor: Monitor,
        store: EventStore,
        defence_enabled: bool,
    ) -> None:
        self.model = model
        self.monitor = monitor
        self.store = store
        self.defence_enabled = defence_enabled
        self._client_counts: dict[str, int] = {}
        self._enforcement: dict[str, str] = {}
        self._restricted_counts: dict[str, int] = {}
        self._lock = threading.RLock()

    def reset(self, monitor: Monitor) -> None:
        with self._lock:
            self.monitor = monitor
            self._client_counts.clear()
            self._enforcement.clear()
            self._restricted_counts.clear()
            self.store.reset()

    def predict(
        self, client_id: str, image: torch.Tensor, timestamp: float
    ) -> PredictionResponse:
        with self._lock:
            return self._predict(client_id, image, timestamp)

    def _predict(
        self, client_id: str, image: torch.Tensor, timestamp: float
    ) -> PredictionResponse:
        if not client_id.strip():
            raise ValueError("client_id must not be empty")
        if len(client_id) > 128:
            raise ValueError("client_id must not exceed 128 characters")
        if image.shape != (1, 28, 28):
            raise ValueError("image must have shape (1, 28, 28)")
        if not torch.isfinite(image).all() or image.min() < 0 or image.max() > 1:
            raise ValueError("image values must be finite and within [0, 1]")

        labels, probabilities, embeddings = predict_batch(self.model, image.unsqueeze(0))
        label = int(labels[0])
        probability_vector = probabilities[0]
        assessment = self.monitor.observe(
            client_id,
            QueryRecord(
                timestamp,
                embeddings[0],
                probability_vector,
                hashlib.blake2b(
                    image.detach().cpu().numpy().tobytes(), digest_size=16
                ).digest(),
            ),
        )

        count = self._client_counts.get(client_id, 0) + 1
        self._client_counts[client_id] = count
        allowed = True
        returned_probabilities: np.ndarray | None = probability_vector
        if self.defence_enabled:
            severity = {"allow": 0, "monitor": 1, "throttle": 2, "block": 3}
            previous = self._enforcement.get(client_id, "allow")
            effective_action = max(
                (previous, assessment.action), key=lambda action: severity[action]
            )
            if effective_action == "throttle":
                restricted_count = self._restricted_counts.get(client_id, 0) + 1
                self._restricted_counts[client_id] = restricted_count
                if restricted_count >= 50:
                    effective_action = "block"
            self._enforcement[client_id] = effective_action
            assessment = replace(assessment, action=effective_action)

            if effective_action == "block":
                allowed = False
                returned_probabilities = None
            elif effective_action == "throttle":
                allowed = self._restricted_counts[client_id] % 5 == 0
                returned_probabilities = None
            elif effective_action == "monitor":
                returned_probabilities = None

        self.store.record(
            timestamp,
            client_id,
            label,
            float(probability_vector[label]),
            assessment,
            allowed,
        )
        return PredictionResponse(
            allowed=allowed,
            label=label if allowed else None,
            probabilities=returned_probabilities if allowed else None,
            assessment=assessment,
        )
