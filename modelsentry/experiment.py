import json
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from .attack import ExtractionResult, run_adaptive_extraction
from .config import ExperimentConfig
from .data import DataPartitions, dataset_to_tensors
from .model import VictimCNN, predict_batch
from .monitor import QueryRecord, StatefulMonitor, fit_benign_profile
from .service import PredictionService
from .store import EventStore


def _records(
    model: VictimCNN, images: torch.Tensor, interval: float, start: float = 0.0
) -> list[QueryRecord]:
    _, probabilities, embeddings = predict_batch(model, images)
    return [
        QueryRecord(start + index * interval, embeddings[index], probabilities[index])
        for index in range(len(images))
    ]


def build_benign_profile(
    model: VictimCNN, calibration_images: torch.Tensor
):
    streams: list[list[QueryRecord]] = []
    session_size = 100
    for session_index, start in enumerate(range(0, len(calibration_images), session_size)):
        images = calibration_images[start : start + session_size]
        if len(images) < session_size:
            break
        interval = 0.05 if session_index % 2 else 0.8
        streams.append(_records(model, images, interval))
    return fit_benign_profile(streams)


def _run_benign_client(
    service: PredictionService,
    images: torch.Tensor,
    client_id: str,
    interval: float,
) -> dict[str, float | int | str]:
    max_risk = 0.0
    final_action = "allow"
    allowed = 0
    for index, image in enumerate(images, start=1):
        response = service.predict(client_id, image, index * interval)
        max_risk = max(max_risk, response.assessment.risk)
        final_action = response.assessment.action
        allowed += int(response.allowed)
    return {
        "requests": len(images),
        "allowed": allowed,
        "max_risk": max_risk,
        "final_action": final_action,
    }


def _new_service(
    model: VictimCNN,
    profile,
    database_path: Path,
    defence_enabled: bool,
) -> tuple[PredictionService, EventStore]:
    store = EventStore(database_path)
    store.reset()
    service = PredictionService(
        model=model,
        monitor=StatefulMonitor(profile),
        store=store,
        defence_enabled=defence_enabled,
    )
    return service, store


def _plot_extraction(
    undefended: ExtractionResult,
    defended: ExtractionResult,
    destination: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for result, label, color in (
        (undefended, "Defence disabled", "#c43d3d"),
        (defended, "ModelSentry enabled", "#147d64"),
    ):
        x = [point.attempted_queries for point in result.points if point.fidelity is not None]
        y = [point.fidelity for point in result.points if point.fidelity is not None]
        axis.plot(x, y, marker="o", linewidth=2.5, label=label, color=color)
    if defended.first_alert_query is not None:
        axis.axvline(
            defended.first_alert_query,
            color="#202020",
            linestyle="--",
            label=f"First alert ({defended.first_alert_query} queries)",
        )
    axis.set_xlabel("Attempted API queries")
    axis.set_ylabel("Surrogate-to-victim fidelity")
    axis.set_ylim(0, 1)
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def run_experiment(
    config: ExperimentConfig,
    model: VictimCNN,
    partitions: DataPartitions,
) -> dict:
    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    calibration_images, _ = dataset_to_tensors(partitions.calibration)
    attack_images, _ = dataset_to_tensors(partitions.attack_pool)
    benign_images, _ = dataset_to_tensors(partitions.benign_evaluation)
    fidelity_images, _ = dataset_to_tensors(partitions.fidelity_evaluation)
    victim_fidelity_labels, _, _ = predict_batch(model, fidelity_images)
    profile = build_benign_profile(model, calibration_images)

    normal_service, normal_store = _new_service(
        model, profile, config.artifacts_dir / "normal.db", defence_enabled=True
    )
    normal = _run_benign_client(normal_service, benign_images[:150], "normal-user", 0.8)
    batch = _run_benign_client(normal_service, benign_images[150:350], "batch-user", 0.05)
    normal_store.close()

    undefended_service, undefended_store = _new_service(
        model, profile, config.artifacts_dir / "undefended.db", defence_enabled=False
    )
    undefended = run_adaptive_extraction(
        undefended_service,
        attack_images,
        fidelity_images,
        victim_fidelity_labels,
        config.query_budgets,
        config.seed,
        "extractor-undefended",
    )
    undefended_store.close()

    defended_service, defended_store = _new_service(
        model, profile, config.artifacts_dir / "defended.db", defence_enabled=True
    )
    defended = run_adaptive_extraction(
        defended_service,
        attack_images,
        fidelity_images,
        victim_fidelity_labels,
        config.query_budgets,
        config.seed,
        "extractor-defended",
    )
    defended_store.close()

    slow_budgets = tuple(budget for budget in config.query_budgets if budget <= 1_000)
    slow_service, slow_store = _new_service(
        model, profile, config.artifacts_dir / "slow_defended.db", defence_enabled=True
    )
    slow_attack = run_adaptive_extraction(
        slow_service,
        attack_images,
        fidelity_images,
        victim_fidelity_labels,
        slow_budgets,
        config.seed,
        "extractor-slow",
        query_interval=0.8,
    )
    slow_store.close()

    rate_only_threshold = float(np.quantile(profile.distributions["rate"], 0.99)) * 1.05
    rate_only = {
        "threshold_queries_per_second": rate_only_threshold,
        "benign_clients_flagged": int((1 / 0.8) > rate_only_threshold)
        + int((1 / 0.05) > rate_only_threshold),
        "benign_clients_tested": 2,
        "fast_attack_detected": (1 / 0.01) > rate_only_threshold,
        "slow_attack_detected": (1 / 0.8) > rate_only_threshold,
    }

    results = {
        "seed": config.seed,
        "normal_client": normal,
        "batch_client": batch,
        "undefended_attack": asdict(undefended),
        "defended_attack": asdict(defended),
        "slow_attack": asdict(slow_attack),
        "rate_only_baseline": rate_only,
        "summary": {
            "benign_clients_blocked": int(normal["allowed"] < normal["requests"])
            + int(batch["allowed"] < batch["requests"]),
            "benign_clients_tested": 2,
            "attack_detected": defended.first_alert_query is not None,
            "slow_attack_detected": slow_attack.first_alert_query is not None,
            "responses_prevented": undefended.responses_received
            - defended.responses_received,
            "undefended_final_fidelity": undefended.points[-1].fidelity,
            "defended_final_fidelity": defended.points[-1].fidelity,
        },
    }
    with (config.artifacts_dir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    _plot_extraction(
        undefended,
        defended,
        config.artifacts_dir / "fidelity_vs_queries.png",
    )
    return results
