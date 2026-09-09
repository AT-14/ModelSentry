import numpy as np

from modelsentry.monitor import (
    BenignProfile,
    QueryRecord,
    StatefulMonitor,
    calculate_signals,
    fit_benign_profile,
)


def make_stream(length: int, interval: float = 1.0) -> list[QueryRecord]:
    records = []
    for index in range(length):
        embedding = np.zeros(4, dtype=np.float32)
        embedding[index % 4] = 1.0
        probabilities = np.full(3, 0.05, dtype=np.float32)
        probabilities[index % 3] = 0.90
        records.append(QueryRecord(index * interval, embedding, probabilities))
    return records


def test_calculated_signals_are_bounded_where_expected() -> None:
    signals = calculate_signals(make_stream(50))
    assert signals["rate"] > 0
    assert 0 <= signals["boundary"] <= 1
    assert 0 <= signals["class_coverage"] <= 1
    assert signals["diversity"] >= 0
    assert signals["acquisition"] >= 0


def test_benign_profile_returns_empirical_percentile() -> None:
    profile = fit_benign_profile([make_stream(100), make_stream(100, 0.1)])
    median_rate = float(np.median(profile.distributions["rate"]))
    percentile = profile.percentile("rate", median_rate)
    assert 0.5 <= percentile <= 1.0


def test_mitigation_requires_persistent_suspicion() -> None:
    profile = BenignProfile(
        {
            name: np.zeros(20)
            for name in ("rate", "diversity", "boundary", "class_coverage", "acquisition")
        }
    )
    monitor = StatefulMonitor(profile, warmup=2)
    stream = make_stream(4, interval=0.01)

    first = monitor.observe("client", stream[0])
    second = monitor.observe("client", stream[1])
    third = monitor.observe("client", stream[2])
    fourth = monitor.observe("client", stream[3])

    assert first.action == "allow"
    assert second.action == "monitor"
    assert third.action == "monitor"
    assert fourth.action == "block"
