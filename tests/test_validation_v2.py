from pathlib import Path

import numpy as np
import pytest

from modelsentry.monitor import BenignProfile
from modelsentry.validation_v2 import BENIGN_PROFILES, summarize_latency
from run_validation_v2 import PROTECTED_EVIDENCE, validate_output_path


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


def test_latency_summary_reports_known_percentiles() -> None:
    summary = summarize_latency([1.0, 2.0, 3.0, 4.0], warmup_samples=2)
    assert summary["samples"] == 4
    assert summary["warmup_samples"] == 2
    assert summary["p50_ms"] == pytest.approx(2.5)
    assert summary["p95_ms"] == pytest.approx(3.85)


def test_profile_percentile_is_empirical_cdf() -> None:
    profile = BenignProfile({"rate": np.array([1.0, 2.0, 3.0])})
    assert profile.percentile("rate", 2.0) == pytest.approx(2 / 3)
