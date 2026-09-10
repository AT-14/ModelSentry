import time
from dataclasses import asdict, dataclass
from math import ceil
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import patch

import numpy as np
import torch

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


DetectorMode = Literal["rate_only", "model_aware", "full", "enhanced"]
ALL_MODES: tuple[DetectorMode, ...] = (
    "rate_only",
    "model_aware",
    "full",
    "enhanced",
)


@dataclass(frozen=True)
class BenignTrafficProfile:
    name: str
    intervals: tuple[float, ...]
    session_size: int = 100
    session_count: int = 6
    long_session_size: int = 500
    long_session_count: int = 1


@dataclass(frozen=True)
class AttackScenario:
    name: str
    query_interval: float
    maximum_queries: int | None = None
    rotating_clients: int = 1
    replay_pool_size: int | None = None


BENIGN_PROFILES = (
    BenignTrafficProfile("interactive", (0.8,)),
    BenignTrafficProfile("batch", (0.05,)),
    BenignTrafficProfile("burst_and_idle", (0.03,) * 10 + (1.5,)),
    BenignTrafficProfile("jittered", (0.45, 0.7, 1.1, 0.6, 0.95)),
    BenignTrafficProfile("mixed_rate", (0.05,) * 5 + (0.8,) * 5),
)

ATTACK_SCENARIOS = (
    AttackScenario("fast_adaptive", 0.01),
    AttackScenario("slow_adaptive", 0.8, maximum_queries=2_000),
    AttackScenario("replay", 0.05, maximum_queries=2_000, replay_pool_size=250),
    AttackScenario("distributed", 0.01, maximum_queries=2_000, rotating_clients=5),
)

ENHANCED_POLICY = {
    "version": "2.4",
    "base_detector": "model_aware_telemetry",
    "linked_identity_separator": ":",
    "persistence_windows": 100,
    "repetition_minimum_queries": 100,
    "repetition_ratio": 0.20,
    "boundary_minimum_windows": 150,
    "boundary_percentile": 0.95,
    "boundary_ratio": 0.60,
    "extreme_rate_multiplier": 2.0,
    "extreme_rate_minimum_queries": 100,
    "linked_account_minimum": 3,
    "linked_account_minimum_queries": 150,
    "campaign_minimum_queries": 400,
    "campaign_boundary_ratio": 0.40,
    "confirmation_windows": 3,
}


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


class EnhancedMonitor:
    def __init__(
        self,
        profile: BenignProfile,
        window_size: int = 50,
        warmup: int = 50,
        persistence_windows: int = ENHANCED_POLICY["persistence_windows"],
        repetition_threshold: float = ENHANCED_POLICY["repetition_ratio"],
    ) -> None:
        self.base = AblationMonitor(
            profile, "model_aware", window_size=window_size, warmup=warmup
        )
        self.persistence_windows = persistence_windows
        self.repetition_threshold = repetition_threshold
        self.monitor_streaks: dict[str, int] = {}
        self.repetition_streaks: dict[str, int] = {}
        self.seen_fingerprints: dict[str, set[bytes]] = {}
        self.duplicate_counts: dict[str, int] = {}
        self.total_counts: dict[str, int] = {}
        self.evaluated_counts: dict[str, int] = {}
        self.critical_boundary_counts: dict[str, int] = {}
        self.boundary_streaks: dict[str, int] = {}
        self.extreme_rate_streaks: dict[str, int] = {}
        self.linked_account_streaks: dict[str, int] = {}
        self.campaign_streaks: dict[str, int] = {}
        self.linked_accounts: dict[str, set[str]] = {}
        self.extreme_rate_threshold = (
            float(profile.distributions["rate"][-1])
            * ENHANCED_POLICY["extreme_rate_multiplier"]
        )

    @staticmethod
    def entity_id(client_id: str) -> str:
        # Production resolvers would use authenticated organization and device
        # metadata. The V2 simulator encodes linked accounts as group:account.
        return client_id.split(ENHANCED_POLICY["linked_identity_separator"], 1)[0]

    def observe(self, client_id: str, record: QueryRecord) -> RiskAssessment:
        entity = self.entity_id(client_id)
        assessment = self.base.observe(entity, record)
        accounts = self.linked_accounts.setdefault(entity, set())
        accounts.add(client_id)

        fingerprint = record.request_fingerprint
        if fingerprint is None:
            fingerprint = np.round(record.embedding, decimals=5).tobytes()
        seen = self.seen_fingerprints.setdefault(entity, set())
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        self.total_counts[entity] = self.total_counts.get(entity, 0) + 1
        self.duplicate_counts[entity] = self.duplicate_counts.get(entity, 0) + int(
            duplicate
        )
        repetition = self.duplicate_counts[entity] / self.total_counts[entity]

        high_non_rate = sum(
            assessment.percentiles.get(name, 0.0) >= 0.95
            for name in SIGNAL_NAMES
            if name != "rate"
        )
        if assessment.action != "allow" and high_non_rate >= 2:
            self.monitor_streaks[entity] = self.monitor_streaks.get(entity, 0) + 1
        else:
            self.monitor_streaks[entity] = 0

        if assessment.percentiles:
            self.evaluated_counts[entity] = self.evaluated_counts.get(entity, 0) + 1
            self.critical_boundary_counts[entity] = self.critical_boundary_counts.get(
                entity, 0
            ) + int(
                assessment.percentiles.get("boundary", 0.0)
                >= ENHANCED_POLICY["boundary_percentile"]
            )
        evaluated = self.evaluated_counts.get(entity, 0)
        boundary_concentration = (
            self.critical_boundary_counts.get(entity, 0) / evaluated
            if evaluated
            else 0.0
        )
        boundary_candidate = (
            evaluated >= ENHANCED_POLICY["boundary_minimum_windows"]
            and boundary_concentration >= ENHANCED_POLICY["boundary_ratio"]
        )
        self.boundary_streaks[entity] = (
            self.boundary_streaks.get(entity, 0) + 1
            if boundary_candidate
            else 0
        )

        repetition_candidate = (
            self.total_counts[entity] >= ENHANCED_POLICY["repetition_minimum_queries"]
            and repetition >= self.repetition_threshold
        )
        self.repetition_streaks[entity] = (
            self.repetition_streaks.get(entity, 0) + 1
            if repetition_candidate
            else 0
        )

        extreme_rate_candidate = (
            self.total_counts[entity]
            >= ENHANCED_POLICY["extreme_rate_minimum_queries"]
            and assessment.signals.get("rate", 0.0) >= self.extreme_rate_threshold
        )
        self.extreme_rate_streaks[entity] = (
            self.extreme_rate_streaks.get(entity, 0) + 1
            if extreme_rate_candidate
            else 0
        )
        linked_account_candidate = (
            len(accounts) >= ENHANCED_POLICY["linked_account_minimum"]
            and self.total_counts[entity]
            >= ENHANCED_POLICY["linked_account_minimum_queries"]
        )
        self.linked_account_streaks[entity] = (
            self.linked_account_streaks.get(entity, 0) + 1
            if linked_account_candidate
            else 0
        )
        campaign_candidate = (
            self.total_counts[entity] >= ENHANCED_POLICY["campaign_minimum_queries"]
            and boundary_concentration
            >= ENHANCED_POLICY["campaign_boundary_ratio"]
        )
        self.campaign_streaks[entity] = (
            self.campaign_streaks.get(entity, 0) + 1
            if campaign_candidate
            else 0
        )

        # Short-window model-aware decisions remain telemetry. Enhanced mode
        # enforces only after an independent long-horizon confirmation below.
        action = "monitor" if assessment.action != "allow" else "allow"
        reasons = list(assessment.reasons)
        if (
            self.monitor_streaks[entity] >= self.persistence_windows
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(0, "persistent model-aware evidence across 100 windows")
        if (
            self.repetition_streaks[entity] >= ENHANCED_POLICY["confirmation_windows"]
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(0, "repeated-query ratio above 20% over long-term history")
        if (
            self.boundary_streaks[entity] >= ENHANCED_POLICY["confirmation_windows"]
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(
                0,
                "boundary probing above the 95th benign percentile in 60% of long-term windows",
            )
        if (
            self.extreme_rate_streaks[entity]
            >= ENHANCED_POLICY["confirmation_windows"]
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(0, "query rate above twice the calibrated benign maximum")
        if (
            self.linked_account_streaks[entity]
            >= ENHANCED_POLICY["confirmation_windows"]
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(0, "coordinated campaign spans at least three linked accounts")
        if (
            self.campaign_streaks[entity] >= ENHANCED_POLICY["confirmation_windows"]
            and action in {"allow", "monitor"}
        ):
            action = "throttle"
            reasons.insert(0, "long campaign exceeds the boundary-heavy acquisition budget")

        signals = {
            **assessment.signals,
            "repetition": repetition,
            "boundary_concentration": boundary_concentration,
            "linked_accounts": float(len(accounts)),
        }
        return RiskAssessment(
            max(assessment.risk, repetition),
            action,
            signals,
            assessment.percentiles,
            tuple(reasons[:3]),
        )


def new_service(
    model: VictimCNN,
    profile: BenignProfile,
    mode: DetectorMode,
    database_path: Path,
) -> tuple[PredictionService, EventStore]:
    store = EventStore(database_path)
    store.reset()
    monitor = (
        EnhancedMonitor(profile)
        if mode == "enhanced"
        else AblationMonitor(profile, mode)
    )
    service = PredictionService(model, monitor, store, True)
    return service, store


def run_benign_sessions(
    service: PredictionService,
    images: torch.Tensor,
    mode: DetectorMode,
    profiles: tuple[BenignTrafficProfile, ...] = BENIGN_PROFILES,
) -> list[dict]:
    results: list[dict] = []
    offset = 0
    full_protocol = len(images) >= 5_000
    for profile in profiles:
        session_sizes = benign_session_sizes(profile, full_protocol)
        for session_index, session_size in enumerate(session_sizes):
            session_images = images[offset : offset + session_size]
            if len(session_images) < session_size:
                raise ValueError("Insufficient benign evaluation images")
            offset += session_size
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


def benign_session_sizes(
    profile: BenignTrafficProfile, full_protocol: bool
) -> list[int]:
    if not full_protocol:
        return [profile.session_size] * 4
    return [profile.long_session_size] * profile.long_session_count + [
        profile.session_size
    ] * (profile.session_count - profile.long_session_count)


class RotatingClientService:
    def __init__(self, service: PredictionService, clients: int, prefix: str) -> None:
        if clients < 1:
            raise ValueError("clients must be positive")
        self.service = service
        self.clients = clients
        self.prefix = prefix
        self.calls = 0

    def predict(self, client_id: str, image: torch.Tensor, timestamp: float) -> PredictionResponse:
        routed_client = f"{self.prefix}:account-{self.calls % self.clients}"
        self.calls += 1
        return self.service.predict(routed_client, image, timestamp)


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
    mode: DetectorMode = "full",
    samples: int = 50,
    warmup: int = 5,
) -> dict:
    from fastapi.testclient import TestClient

    service, store = new_service(
        model, profile, mode, output_dir / f"latency_service_{mode}.db"
    )
    service_times: list[float] = []
    for index in range(warmup + samples):
        started = time.perf_counter_ns()
        service.predict("latency-service", image, index * 0.8)
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if index >= warmup:
            service_times.append(elapsed)
    store.close()

    api_service, api_store = new_service(
        model, profile, mode, output_dir / f"latency_api_{mode}.db"
    )
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


def scenario_budgets(
    budgets: tuple[int, ...], scenario: AttackScenario
) -> tuple[int, ...]:
    maximum = max(budgets)
    if scenario.maximum_queries is not None:
        maximum = min(maximum, scenario.maximum_queries)
    selected = tuple(budget for budget in budgets if budget <= maximum)
    if maximum not in selected:
        selected += (maximum,)
    return selected


def scenario_pool(
    attack_images: torch.Tensor,
    scenario: AttackScenario,
    maximum_queries: int,
) -> torch.Tensor:
    if scenario.replay_pool_size is None:
        return attack_images
    source = attack_images[: scenario.replay_pool_size]
    if len(source) == 0:
        raise ValueError("Replay scenario requires attack images")
    repeats = ceil(maximum_queries / len(source))
    return source.repeat((repeats, 1, 1, 1))[:maximum_queries]


def run_attack_scenario(
    model: VictimCNN,
    profile: BenignProfile,
    mode: DetectorMode,
    scenario: AttackScenario,
    attack_images: torch.Tensor,
    fidelity_images: torch.Tensor,
    victim_fidelity_labels: np.ndarray,
    budgets: tuple[int, ...],
    seed: int,
    output_dir: Path,
) -> dict:
    effective_budgets = scenario_budgets(budgets, scenario)
    pool = scenario_pool(attack_images, scenario, max(effective_budgets))
    service, store = new_service(
        model,
        profile,
        mode,
        output_dir / f"attack_{mode}_{scenario.name}.db",
    )
    routed_service = (
        RotatingClientService(service, scenario.rotating_clients, f"v2-{scenario.name}")
        if scenario.rotating_clients > 1
        else service
    )
    probe = AlertFidelityProbe(
        routed_service, fidelity_images, victim_fidelity_labels, seed
    )
    extraction = run_adaptive_extraction(
        probe,
        pool,
        fidelity_images,
        victim_fidelity_labels,
        effective_budgets,
        seed,
        f"v2-extractor-{mode}-{scenario.name}",
        query_interval=scenario.query_interval,
    )
    store.close()
    return {
        **asdict(extraction),
        "answered_queries_at_first_alert": probe.answered_at_alert,
        "fidelity_at_first_alert": probe.fidelity_at_alert,
        "query_interval": scenario.query_interval,
        "rotating_clients": scenario.rotating_clients,
        "replay_pool_size": scenario.replay_pool_size,
        "maximum_queries": max(effective_budgets),
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
    modes: tuple[DetectorMode, ...] = ALL_MODES,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = build_extended_benign_profile(model, calibration_images)
    mode_results: dict[str, dict] = {}
    for mode in modes:
        benign_service, benign_store = new_service(
            model, profile, mode, output_dir / f"benign_{mode}.db"
        )
        benign = run_benign_sessions(benign_service, benign_images, mode)
        benign_store.close()

        mode_results[mode] = {
            "benign_sessions": benign,
            "attacks": {
                scenario.name: run_attack_scenario(
                    model,
                    profile,
                    mode,
                    scenario,
                    attack_images,
                    fidelity_images,
                    victim_fidelity_labels,
                    budgets,
                    seed,
                    output_dir,
                )
                for scenario in ATTACK_SCENARIOS
            },
        }
    for mode in (mode for mode in ("full", "enhanced") if mode in mode_results):
        mode_results[mode]["latency"] = measure_latency(
            model, profile, benign_images[0], output_dir, mode=mode
        )
    return {
        "schema_version": 2,
        "seed": seed,
        "profiles": [asdict(profile) for profile in BENIGN_PROFILES],
        "effective_benign_sessions_per_mode": len(
            next(iter(mode_results.values()))["benign_sessions"]
        ),
        "detector_modes_evaluated": list(modes),
        "attack_scenarios": [asdict(scenario) for scenario in ATTACK_SCENARIOS],
        "enhanced_policy": ENHANCED_POLICY,
        "alert_definition": "first throttle or block action",
        "detector_modes": mode_results,
    }
