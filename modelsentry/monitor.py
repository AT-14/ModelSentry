from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

import numpy as np


SIGNAL_NAMES = ("rate", "diversity", "boundary", "class_coverage", "acquisition")
SIGNAL_WEIGHTS = np.array([0.15, 0.20, 0.25, 0.15, 0.25], dtype=np.float64)


@dataclass(frozen=True)
class QueryRecord:
    timestamp: float
    embedding: np.ndarray
    probabilities: np.ndarray
    request_fingerprint: bytes | None = None


@dataclass(frozen=True)
class RiskAssessment:
    risk: float
    action: str
    signals: dict[str, float]
    percentiles: dict[str, float]
    reasons: tuple[str, ...]


class Monitor(Protocol):
    def observe(self, client_id: str, record: QueryRecord) -> RiskAssessment: ...


@dataclass(frozen=True)
class BenignProfile:
    distributions: dict[str, np.ndarray]

    def percentile(self, signal: str, value: float) -> float:
        reference = self.distributions[signal]
        return float(np.searchsorted(reference, value, side="right") / len(reference))


def calculate_signals(records: list[QueryRecord]) -> dict[str, float]:
    if len(records) < 2:
        return {name: 0.0 for name in SIGNAL_NAMES}

    timestamps = np.array([record.timestamp for record in records], dtype=np.float64)
    embeddings = np.stack([record.embedding for record in records]).astype(np.float64)
    probabilities = np.stack([record.probabilities for record in records]).astype(np.float64)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / np.maximum(norms, 1e-12)
    consecutive_distances = np.linalg.norm(np.diff(normalized, axis=0), axis=1)

    sorted_probabilities = np.sort(probabilities, axis=1)
    margins = sorted_probabilities[:, -1] - sorted_probabilities[:, -2]
    labels = probabilities.argmax(axis=1)
    counts = np.bincount(labels, minlength=probabilities.shape[1]).astype(np.float64)
    class_distribution = counts[counts > 0] / len(labels)
    class_entropy = -np.sum(class_distribution * np.log(class_distribution))
    normalized_entropy = class_entropy / np.log(probabilities.shape[1])

    acquisition_values: list[float] = []
    for index in range(1, len(normalized)):
        novelty = float(np.min(np.linalg.norm(normalized[:index] - normalized[index], axis=1)))
        boundary_value = 1.0 - float(np.clip(margins[index], 0.0, 1.0))
        acquisition_values.append(novelty * boundary_value)

    duration = max(float(timestamps[-1] - timestamps[0]), 1e-6)
    return {
        "rate": (len(records) - 1) / duration,
        "diversity": float(np.mean(consecutive_distances)),
        "boundary": float(np.mean(margins < 0.20)),
        "class_coverage": float(normalized_entropy),
        "acquisition": float(np.mean(acquisition_values)),
    }


def fit_benign_profile(streams: list[list[QueryRecord]], window_size: int = 50) -> BenignProfile:
    if not streams:
        raise ValueError("Calibration requires benign query streams")
    split_index = max(1, int(len(streams) * 0.70))
    reference_streams = streams[:split_index]
    observed: dict[str, list[float]] = {name: [] for name in SIGNAL_NAMES}
    for stream in reference_streams:
        for end in range(window_size, len(stream) + 1, 10):
            signals = calculate_signals(stream[max(0, end - window_size) : end])
            for name, value in signals.items():
                observed[name].append(value)
    if any(not values for values in observed.values()):
        raise ValueError("Calibration requires at least one complete query window")
    distributions = {
        name: np.sort(np.asarray(values, dtype=np.float64))
        for name, values in observed.items()
    }
    return BenignProfile(distributions)


class StatefulMonitor:
    def __init__(
        self,
        profile: BenignProfile,
        window_size: int = 50,
        warmup: int = 50,
    ) -> None:
        self.profile = profile
        self.window_size = window_size
        self.warmup = warmup
        self._history: dict[str, deque[QueryRecord]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._suspicious_streak: dict[str, int] = defaultdict(int)

    def observe(self, client_id: str, record: QueryRecord) -> RiskAssessment:
        history = self._history[client_id]
        history.append(record)
        signals = calculate_signals(list(history))
        if len(history) < self.warmup:
            return RiskAssessment(0.0, "allow", signals, {}, ())

        percentiles = {
            name: self.profile.percentile(name, value) for name, value in signals.items()
        }
        percentile_vector = np.array(
            [percentiles[name] for name in SIGNAL_NAMES], dtype=np.float64
        )
        # Ignore the ordinary middle of the benign distribution and accumulate
        # evidence only above its 75th percentile.
        evidence = np.clip((percentile_vector - 0.75) / 0.25, 0.0, 1.0)
        risk = float(np.dot(SIGNAL_WEIGHTS, evidence))

        non_rate = [percentiles[name] for name in SIGNAL_NAMES if name != "rate"]
        high_non_rate = sum(percentile >= 0.95 for percentile in non_rate)
        critical_non_rate = sum(percentile >= 0.99 for percentile in non_rate)
        rate_is_high = percentiles["rate"] >= 0.99

        # Escalation requires several independent signals. Their 95th/99th
        # percentile cutoffs are established only from benign reference traffic.
        if rate_is_high and critical_non_rate >= 3:
            candidate_action = "block"
        elif (rate_is_high and high_non_rate >= 2) or high_non_rate >= 3:
            candidate_action = "throttle"
        elif high_non_rate >= 2:
            candidate_action = "monitor"
        else:
            candidate_action = "allow"

        if candidate_action in {"throttle", "block"}:
            self._suspicious_streak[client_id] += 1
        else:
            self._suspicious_streak[client_id] = 0
        if candidate_action in {"throttle", "block"} and self._suspicious_streak[client_id] >= 3:
            action = candidate_action
        elif candidate_action != "allow":
            action = "monitor"
        else:
            action = "allow"

        ranked = sorted(
            ((percentiles[name], name) for name in SIGNAL_NAMES), reverse=True
        )
        reasons = tuple(
            f"{name.replace('_', ' ')} above {percentile * 100:.0f}% of benign windows"
            for percentile, name in ranked[:3]
            if percentile >= 0.90
        )
        return RiskAssessment(risk, action, signals, percentiles, reasons)
