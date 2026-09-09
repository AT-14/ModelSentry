import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import patch

import numpy as np
import torch
from fastapi.testclient import TestClient

from .api import create_app
from .attack import _fit_surrogate, run_adaptive_extraction
from .model import VictimCNN, predict_batch
from .monitor import (
    SIGNAL_NAMES,
    BenignProfile,
    QueryRecord,
    RiskAssessment,
    StatefulMonitor,
    calculate_signals,
    fit_benign_profile,
)
from .service import PredictionResponse, PredictionService
from .store import EventStore


DetectorMode = Literal["rate_only", "model_aware", "full"]


@dataclass(frozen=True)
class BenignTrafficProfile:
    name: str
    intervals: tuple[float, ...]
    session_size: int = 100
    session_count: int = 2


BENIGN_PROFILES = (
    BenignTrafficProfile("interactive", (0.8,)),
    BenignTrafficProfile("batch", (0.05,)),
    BenignTrafficProfile("burst_and_idle", (0.03,) * 10 + (1.5,)),
    BenignTrafficProfile("jittered", (0.45, 0.7, 1.1, 0.6, 0.95)),
    BenignTrafficProfile("mixed_rate", (0.05,) * 5 + (0.8,) * 5),
)


def _records(
    model: VictimCNN,
    images: torch.Tensor,
    intervals: tuple[float, ...],
) -> list[QueryRecord]:
    _, probabilities, embeddings = predict_batch(model, images)
    timestamps: list[float] = []
    current = 0.0
    for index in range(len(images)):
        current += intervals[index % len(intervals)]
        timestamps.append(current)
    return [
        QueryRecord(timestamps[index], embeddings[index], probabilities[index])
        for index in range(len(images))
    ]


def build_extended_benign_profile(
    model: VictimCNN,
    calibration_images: torch.Tensor,
    profiles: tuple[BenignTrafficProfile, ...] = BENIGN_PROFILES,
) -> BenignProfile:
    session_size = profiles[0].session_size
    streams: list[list[QueryRecord]] = []
    for index, start in enumerate(range(0, len(calibration_images), session_size)):
        images = calibration_images[start : start + session_size]
        if len(images) < session_size:
            break
        profile = profiles[index % len(profiles)]
        streams.append(_records(model, images, profile.intervals))
    if len(streams) < len(profiles):
        raise ValueError("Calibration data must contain at least one session per profile")
    return fit_benign_profile(streams)


class AblationMonitor:
    def __init__(
        self,
        profile: BenignProfile,
        mode: DetectorMode,
        window_size: int = 50,
        warmup: int = 50,
    ) -> None:
        self.profile = profile
        self.mode = mode
        self.window_size = window_size
        self.warmup = warmup
        self.full = StatefulMonitor(profile, window_size, warmup) if mode == "full" else None
        self.history: dict[str, list[QueryRecord]] = {}
        self.streaks: dict[str, int] = {}

    def observe(self, client_id: str, record: QueryRecord) -> RiskAssessment:
        if self.full is not None:
            return self.full.observe(client_id, record)
        history = self.history.setdefault(client_id, [])
        history.append(record)
        del history[:-self.window_size]
        signals = calculate_signals(history)
        if len(history) < self.warmup:
            return RiskAssessment(0.0, "allow", signals, {}, ())
        percentiles = {
            name: self.profile.percentile(name, value) for name, value in signals.items()
        }
        if self.mode == "rate_only":
            risk = percentiles["rate"]
            candidate = "throttle" if percentiles["rate"] >= 0.99 else "allow"
            selected = ("rate",)
        else:
            selected = tuple(name for name in SIGNAL_NAMES if name != "rate")
            high = sum(percentiles[name] >= 0.95 for name in selected)
            critical = sum(percentiles[name] >= 0.99 for name in selected)
            risk = float(np.mean([percentiles[name] for name in selected]))
            if critical >= 3:
                candidate = "block"
            elif high >= 3:
                candidate = "throttle"
            elif high >= 2:
                candidate = "monitor"
            else:
                candidate = "allow"
        self.streaks[client_id] = (
            self.streaks.get(client_id, 0) + 1
            if candidate in {"throttle", "block"}
            else 0
        )
        if candidate in {"throttle", "block"} and self.streaks[client_id] < 3:
            action = "monitor"
        else:
            action = candidate
        reasons = tuple(
            f"{name.replace('_', ' ')} above {percentiles[name] * 100:.0f}% of benign windows"
            for name in selected
            if percentiles[name] >= 0.90
        )
        return RiskAssessment(risk, action, signals, percentiles, reasons[:3])


def new_service(
    model: VictimCNN,
    profile: BenignProfile,
    mode: DetectorMode,
    database_path: Path,
) -> tuple[PredictionService, EventStore]:
    store = EventStore(database_path)
    store.reset()
    service = PredictionService(model, AblationMonitor(profile, mode), store, True)
    return service, store


def run_benign_sessions(
    service: PredictionService,
    images: torch.Tensor,
    mode: DetectorMode,
    profiles: tuple[BenignTrafficProfile, ...] = BENIGN_PROFILES,
) -> list[dict]:
    results: list[dict] = []
    offset = 0
    for profile in profiles:
        for session_index in range(profile.session_count):
            session_images = images[offset : offset + profile.session_size]
            if len(session_images) < profile.session_size:
                raise ValueError("Insufficient benign evaluation images")
            offset += profile.session_size
            allowed = 0
            max_risk = 0.0
            first_alert = None
            final_action = "allow"
            timestamp = 0.0
            client_id = f"v2-{mode}-{profile.name}-{session_index}"
            for query, image in enumerate(session_images, start=1):
                timestamp += profile.intervals[(query - 1) % len(profile.intervals)]
                response = service.predict(client_id, image, timestamp)
                allowed += int(response.allowed)
                max_risk = max(max_risk, response.assessment.risk)
                final_action = response.assessment.action
                if first_alert is None and final_action in {"throttle", "block"}:
                    first_alert = query
            results.append(
                {
                    "mode": mode,
                    "profile": profile.name,
                    "session_id": client_id,
                    "requests": len(session_images),
                    "allowed": allowed,
                    "first_alert_query": first_alert,
                    "max_risk": max_risk,
                    "final_action": final_action,
                }
            )
    return results


class AlertFidelityProbe:
    def __init__(
        self,
        service: PredictionService,
        fidelity_images: torch.Tensor,
        victim_labels: np.ndarray,
        seed: int,
    ) -> None:
        self.service = service
        self.fidelity_inputs = fidelity_images.numpy().reshape(len(fidelity_images), -1)
        self.victim_labels = victim_labels
        self.seed = seed
        self.calls = 0
        self.images: list[np.ndarray] = []
        self.labels: list[int] = []
        self.first_alert_query: int | None = None
        self.answered_at_alert: int | None = None
        self.fidelity_at_alert: float | None = None

    def predict(self, client_id: str, image: torch.Tensor, timestamp: float) -> PredictionResponse:
        self.calls += 1
        response = self.service.predict(client_id, image, timestamp)
        if response.allowed and response.label is not None:
            self.images.append(image.numpy().reshape(-1))
            self.labels.append(response.label)
        if self.first_alert_query is None and response.assessment.action in {"throttle", "block"}:
            self.first_alert_query = self.calls
            self.answered_at_alert = len(self.labels)
            surrogate = _fit_surrogate(self.images, self.labels, self.seed)
            if surrogate is not None:
                predictions = surrogate.predict(self.fidelity_inputs)
                self.fidelity_at_alert = float(np.mean(predictions == self.victim_labels))
        return response


def summarize_latency(samples_ms: list[float], warmup_samples: int) -> dict:
    values = np.asarray(samples_ms, dtype=np.float64)
    return {
        "samples": len(samples_ms),
        "warmup_samples": warmup_samples,
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
    }


def measure_latency(
    model: VictimCNN,
    profile: BenignProfile,
    image: torch.Tensor,
    output_dir: Path,
    samples: int = 50,
    warmup: int = 5,
) -> dict:
    service, store = new_service(model, profile, "full", output_dir / "latency_service.db")
    service_times: list[float] = []
    for index in range(warmup + samples):
        started = time.perf_counter_ns()
        service.predict("latency-service", image, index * 0.8)
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if index >= warmup:
            service_times.append(elapsed)
    store.close()

    api_service, api_store = new_service(model, profile, "full", output_dir / "latency_api.db")
    client = TestClient(create_app(api_service))
    payload = {"pixels": image.numpy().reshape(-1).tolist()}
    api_times: list[float] = []
    timestamps = iter(index * 0.8 for index in range(warmup + samples))
    api_clock = SimpleNamespace(time=lambda: next(timestamps))
    with patch("modelsentry.api.time", api_clock):
        for index in range(warmup + samples):
            started = time.perf_counter_ns()
            response = client.post("/predict", json=payload, headers={"X-API-Key": "latency-api"})
            response.raise_for_status()
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            if index >= warmup:
                api_times.append(elapsed)
    api_store.close()
    return {
        "service_end_to_end": summarize_latency(service_times, warmup),
        "api_in_process": summarize_latency(api_times, warmup),
    }


def run_extended_experiment(
    model: VictimCNN,
    calibration_images: torch.Tensor,
    benign_images: torch.Tensor,
    attack_images: torch.Tensor,
    fidelity_images: torch.Tensor,
    victim_fidelity_labels: np.ndarray,
    budgets: tuple[int, ...],
    seed: int,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = build_extended_benign_profile(model, calibration_images)
    mode_results: dict[str, dict] = {}
    for mode in ("rate_only", "model_aware", "full"):
        benign_service, benign_store = new_service(
            model, profile, mode, output_dir / f"benign_{mode}.db"
        )
        benign = run_benign_sessions(benign_service, benign_images, mode)
        benign_store.close()

        attack_service, attack_store = new_service(
            model, profile, mode, output_dir / f"attack_{mode}.db"
        )
        probe = AlertFidelityProbe(attack_service, fidelity_images, victim_fidelity_labels, seed)
        extraction = run_adaptive_extraction(
            probe,
            attack_images,
            fidelity_images,
            victim_fidelity_labels,
            budgets,
            seed,
            f"v2-extractor-{mode}",
        )
        attack_store.close()
        mode_results[mode] = {
            "benign_sessions": benign,
            "fast_attack": {
                **asdict(extraction),
                "answered_queries_at_first_alert": probe.answered_at_alert,
                "fidelity_at_first_alert": probe.fidelity_at_alert,
            },
        }
    mode_results["full"]["latency"] = measure_latency(
        model, profile, benign_images[0], output_dir
    )
    return {
        "schema_version": 2,
        "seed": seed,
        "profiles": [asdict(profile) for profile in BENIGN_PROFILES],
        "alert_definition": "first throttle or block action",
        "detector_modes": mode_results,
    }
