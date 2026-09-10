from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import torch

from modelsentry.config import ExperimentConfig
from modelsentry.monitor import SIGNAL_NAMES, BenignProfile, QueryRecord, RiskAssessment
from modelsentry.service import PredictionResponse
from modelsentry.validation_v2 import (
    ATTACK_SCENARIOS,
    BENIGN_PROFILES,
    AblationMonitor,
    AlertFidelityProbe,
    EnhancedMonitor,
    RotatingClientService,
    benign_session_sizes,
    scenario_budgets,
    scenario_pool,
    summarize_latency,
)
from run_validation_v2 import (
    PROTECTED_EVIDENCE,
    protocol_signature,
    validate_output_path,
)


def test_v2_output_guard_rejects_baseline_and_descendants() -> None:
    with pytest.raises(ValueError):
        validate_output_path(PROTECTED_EVIDENCE)
    with pytest.raises(ValueError):
        validate_output_path(PROTECTED_EVIDENCE / "new")


def test_v2_output_guard_accepts_isolated_directory() -> None:
    path = validate_output_path(Path("artifacts/validation_extended_v2"))
    assert path.name == "validation_extended_v2"


def test_profiles_cover_distinct_timing_shapes() -> None:
    assert len(BENIGN_PROFILES) == 5
    assert len({profile.name for profile in BENIGN_PROFILES}) == len(BENIGN_PROFILES)
    assert all(profile.session_size >= 50 for profile in BENIGN_PROFILES)
    assert len({profile.intervals for profile in BENIGN_PROFILES}) == len(BENIGN_PROFILES)
    assert sum(profile.session_count for profile in BENIGN_PROFILES) == 30
    assert sum(
        sum(benign_session_sizes(profile, False)) for profile in BENIGN_PROFILES
    ) == 2_000
    assert sum(
        sum(benign_session_sizes(profile, True)) for profile in BENIGN_PROFILES
    ) == 5_000


def test_attack_scenarios_cover_required_evasions() -> None:
    assert {scenario.name for scenario in ATTACK_SCENARIOS} == {
        "fast_adaptive",
        "slow_adaptive",
        "replay",
        "distributed",
    }
    distributed = next(item for item in ATTACK_SCENARIOS if item.name == "distributed")
    replay = next(item for item in ATTACK_SCENARIOS if item.name == "replay")
    assert distributed.rotating_clients == 5
    assert replay.replay_pool_size == 250


def test_latency_summary_reports_known_percentiles() -> None:
    summary = summarize_latency([1.0, 2.0, 3.0, 4.0], warmup_samples=2)
    assert summary["samples"] == 4
    assert summary["warmup_samples"] == 2
    assert summary["p50_ms"] == pytest.approx(2.5)
    assert summary["p95_ms"] == pytest.approx(3.85)


def test_profile_percentile_is_empirical_cdf() -> None:
    profile = BenignProfile({"rate": np.array([1.0, 2.0, 3.0])})
    assert profile.percentile("rate", 2.0) == pytest.approx(2 / 3)


def test_rate_only_and_model_aware_modes_use_separate_evidence() -> None:
    profile = BenignProfile(
        {name: np.array([0.0, 1.0], dtype=np.float64) for name in SIGNAL_NAMES}
    )
    record = QueryRecord(0.0, np.ones(2), np.array([0.5, 0.5]))
    rate_only_signals = {name: 0.0 for name in SIGNAL_NAMES}
    rate_only_signals["rate"] = 2.0
    with patch("modelsentry.validation_v2.calculate_signals", return_value=rate_only_signals):
        rate_monitor = AblationMonitor(profile, "rate_only", window_size=2, warmup=2)
        rate_actions = [rate_monitor.observe("client", record).action for _ in range(4)]
        aware_monitor = AblationMonitor(profile, "model_aware", window_size=2, warmup=2)
        aware_actions = [aware_monitor.observe("client", record).action for _ in range(4)]
    assert rate_actions == ["allow", "monitor", "monitor", "throttle"]
    assert aware_actions == ["allow", "allow", "allow", "allow"]

    aware_signals = {name: 2.0 for name in SIGNAL_NAMES}
    aware_signals["rate"] = 0.0
    with patch("modelsentry.validation_v2.calculate_signals", return_value=aware_signals):
        aware_monitor = AblationMonitor(profile, "model_aware", window_size=2, warmup=2)
        aware_actions = [aware_monitor.observe("client", record).action for _ in range(4)]
    assert aware_actions == ["allow", "monitor", "monitor", "block"]


def test_rotating_service_distributes_requests_across_accounts() -> None:
    class FakeService:
        def __init__(self) -> None:
            self.clients: list[str] = []

        def predict(self, client_id, image, timestamp):
            self.clients.append(client_id)
            return "response"

    service = FakeService()
    rotating = RotatingClientService(service, clients=3, prefix="sybil")
    responses = [rotating.predict("ignored", None, float(index)) for index in range(5)]
    assert responses == ["response"] * 5
    assert service.clients == [
        "sybil:account-0",
        "sybil:account-1",
        "sybil:account-2",
        "sybil:account-0",
        "sybil:account-1",
    ]


def test_enhanced_monitor_correlates_linked_accounts() -> None:
    assert EnhancedMonitor.entity_id("organization:account-1") == "organization"
    assert EnhancedMonitor.entity_id("independent-client") == "independent-client"


def test_enhanced_monitor_detects_long_term_repetition() -> None:
    profile = BenignProfile(
        {name: np.array([100.0], dtype=np.float64) for name in SIGNAL_NAMES}
    )
    monitor = EnhancedMonitor(profile, persistence_windows=100)
    probabilities = np.array([0.9, 0.1])
    actions = [
        monitor.observe(
            "client",
            QueryRecord(
                float(index),
                np.array([1.0, 2.0]),
                probabilities,
                request_fingerprint=b"repeated-request",
            ),
        ).action
        for index in range(102)
    ]
    assert actions[-1] == "throttle"


def test_enhanced_monitor_escalates_persistent_model_aware_evidence() -> None:
    class MonitorStub:
        def observe(self, client_id, record):
            percentiles = {name: 1.0 for name in SIGNAL_NAMES}
            percentiles["rate"] = 0.0
            return RiskAssessment(0.5, "monitor", {}, percentiles, ())

    profile = BenignProfile(
        {
            name: np.array([100.0 if name == "rate" else 0.0])
            for name in SIGNAL_NAMES
        }
    )
    monitor = EnhancedMonitor(profile, persistence_windows=3)
    monitor.base = MonitorStub()
    probabilities = np.array([0.9, 0.1])
    actions = [
        monitor.observe(
            "client",
            QueryRecord(float(index), np.array([float(index)]), probabilities),
        ).action
        for index in range(3)
    ]
    assert actions == ["monitor", "monitor", "throttle"]


def test_enhanced_monitor_detects_long_horizon_boundary_concentration() -> None:
    class MonitorStub:
        def observe(self, client_id, record):
            percentiles = {name: 0.0 for name in SIGNAL_NAMES}
            percentiles["boundary"] = 1.0
            return RiskAssessment(0.25, "monitor", {}, percentiles, ())

    profile = BenignProfile(
        {
            name: np.array([100.0 if name == "rate" else 0.0])
            for name in SIGNAL_NAMES
        }
    )
    monitor = EnhancedMonitor(profile, persistence_windows=1_000)
    monitor.base = MonitorStub()
    probabilities = np.array([0.9, 0.1])
    actions = []
    for index in range(152):
        actions.append(
            monitor.observe(
                "client",
                QueryRecord(
                    float(index),
                    np.array([float(index)]),
                    probabilities,
                    request_fingerprint=index.to_bytes(4, "little"),
                ),
            ).action
        )
    assert actions[-2:] == ["monitor", "throttle"]


def test_enhanced_monitor_does_not_enforce_short_window_decision_alone() -> None:
    class MonitorStub:
        def observe(self, client_id, record):
            percentiles = {name: 1.0 for name in SIGNAL_NAMES}
            return RiskAssessment(1.0, "block", {}, percentiles, ())

    profile = BenignProfile(
        {name: np.array([0.0], dtype=np.float64) for name in SIGNAL_NAMES}
    )
    monitor = EnhancedMonitor(profile)
    monitor.base = MonitorStub()
    assessment = monitor.observe(
        "client",
        QueryRecord(
            0.0,
            np.array([1.0]),
            np.array([0.9, 0.1]),
            request_fingerprint=b"unique",
        ),
    )
    assert assessment.action == "monitor"


def test_enhanced_monitor_detects_extreme_rate_after_confirmation() -> None:
    class MonitorStub:
        def observe(self, client_id, record):
            return RiskAssessment(
                0.0,
                "allow",
                {"rate": 25.0},
                {name: 0.0 for name in SIGNAL_NAMES},
                (),
            )

    distributions = {
        name: np.array([10.0 if name == "rate" else 100.0])
        for name in SIGNAL_NAMES
    }
    monitor = EnhancedMonitor(BenignProfile(distributions))
    monitor.base = MonitorStub()
    actions = []
    for index in range(102):
        actions.append(
            monitor.observe(
                "client",
                QueryRecord(
                    float(index),
                    np.array([float(index)]),
                    np.array([0.9, 0.1]),
                    request_fingerprint=index.to_bytes(4, "little"),
                ),
            ).action
        )
    assert actions[-2:] == ["allow", "throttle"]


def test_enhanced_monitor_detects_linked_account_campaign() -> None:
    class MonitorStub:
        def observe(self, client_id, record):
            return RiskAssessment(
                0.0,
                "allow",
                {"rate": 0.0},
                {name: 0.0 for name in SIGNAL_NAMES},
                (),
            )

    profile = BenignProfile(
        {name: np.array([100.0], dtype=np.float64) for name in SIGNAL_NAMES}
    )
    monitor = EnhancedMonitor(profile)
    monitor.base = MonitorStub()
    actions = []
    for index in range(152):
        actions.append(
            monitor.observe(
                f"organization:account-{index % 3}",
                QueryRecord(
                    float(index),
                    np.array([float(index)]),
                    np.array([0.9, 0.1]),
                    request_fingerprint=index.to_bytes(4, "little"),
                ),
            ).action
        )
    assert actions[-2:] == ["allow", "throttle"]


def test_alert_probe_records_exact_answer_count() -> None:
    class FakeService:
        def __init__(self) -> None:
            self.calls = 0

        def predict(self, client_id, image, timestamp):
            self.calls += 1
            action = "throttle" if self.calls == 3 else "allow"
            assessment = RiskAssessment(0.9, action, {}, {}, ())
            return PredictionResponse(True, self.calls % 2, None, assessment)

    probe = AlertFidelityProbe(
        FakeService(),
        torch.zeros((2, 1, 28, 28)),
        np.array([0, 1]),
        seed=42,
    )
    image = torch.zeros((1, 28, 28))
    for index in range(4):
        probe.predict("client", image, float(index))
    assert probe.first_alert_query == 3
    assert probe.answered_at_alert == 3
    assert probe.fidelity_at_alert is None


def test_scenario_caps_and_replay_pool_are_deterministic() -> None:
    replay = next(item for item in ATTACK_SCENARIOS if item.name == "replay")
    assert scenario_budgets((100, 250, 500, 1_000, 5_000), replay) == (
        100,
        250,
        500,
        1_000,
        2_000,
    )
    images = torch.arange(300, dtype=torch.float32).reshape(300, 1, 1, 1)
    pool = scenario_pool(images, replay, 600)
    assert len(pool) == 600
    assert pool[0].item() == pool[250].item() == pool[500].item()


def test_protocol_signature_changes_with_effective_settings() -> None:
    first = protocol_signature(42, ExperimentConfig(seed=42, epochs=1))
    assert first == protocol_signature(42, ExperimentConfig(seed=42, epochs=1))
    assert first != protocol_signature(42, ExperimentConfig(seed=42, epochs=2))
    assert first != protocol_signature(7, ExperimentConfig(seed=7, epochs=1))
    assert first != protocol_signature(
        42, ExperimentConfig(seed=42, epochs=1), ("full", "enhanced")
    )
    assert first != protocol_signature(
        42,
        ExperimentConfig(seed=42, epochs=1, benign_evaluation_size=5_000),
    )
