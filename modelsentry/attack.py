from dataclasses import dataclass

import numpy as np
import torch
from sklearn.linear_model import SGDClassifier

from .service import PredictionService


@dataclass(frozen=True)
class ExtractionPoint:
    attempted_queries: int
    answered_queries: int
    fidelity: float | None


@dataclass(frozen=True)
class ExtractionResult:
    points: tuple[ExtractionPoint, ...]
    first_alert_query: int | None
    first_block_query: int | None
    final_risk: float
    responses_received: int


def _fit_surrogate(
    images: list[np.ndarray], labels: list[int], seed: int
) -> SGDClassifier | None:
    if len(images) < 20 or len(set(labels)) < 2:
        return None
    classifier = SGDClassifier(
        loss="log_loss",
        alpha=1e-4,
        max_iter=2_000,
        tol=1e-3,
        random_state=seed,
    )
    classifier.fit(np.stack(images), np.asarray(labels))
    return classifier


def run_adaptive_extraction(
    service: PredictionService,
    pool_images: torch.Tensor,
    fidelity_images: torch.Tensor,
    victim_fidelity_labels: np.ndarray,
    budgets: tuple[int, ...],
    seed: int,
    client_id: str,
    query_interval: float = 0.01,
) -> ExtractionResult:
    rng = np.random.default_rng(seed)
    flattened_pool = pool_images.numpy().reshape(len(pool_images), -1)
    flattened_fidelity = fidelity_images.numpy().reshape(len(fidelity_images), -1)
    remaining = list(rng.permutation(len(pool_images)))
    queried_images: list[np.ndarray] = []
    returned_labels: list[int] = []
    points: list[ExtractionPoint] = []
    first_alert: int | None = None
    first_block: int | None = None
    final_risk = 0.0
    surrogate: SGDClassifier | None = None
    fitted_response_count = 0
    batch_size = 50
    max_budget = max(budgets)
    attempted = 0

    while attempted < max_budget and remaining:
        if surrogate is None:
            selected = remaining[:batch_size]
        else:
            candidates = np.asarray(remaining)
            probabilities = surrogate.predict_proba(flattened_pool[candidates])
            if probabilities.shape[1] < 2:
                selected = remaining[:batch_size]
            else:
                top_two = np.partition(probabilities, -2, axis=1)[:, -2:]
                margins = np.abs(top_two[:, 1] - top_two[:, 0])
                selected = candidates[np.argsort(margins)[:batch_size]].tolist()

        selected_set = set(selected)
        remaining = [index for index in remaining if index not in selected_set]
        for index in selected:
            if attempted >= max_budget:
                break
            attempted += 1
            response = service.predict(
                client_id,
                pool_images[index],
                timestamp=attempted * query_interval,
            )
            final_risk = response.assessment.risk
            if response.assessment.action in {"throttle", "block"} and first_alert is None:
                first_alert = attempted
            if not response.allowed and first_block is None:
                first_block = attempted
            if response.allowed and response.label is not None:
                queried_images.append(flattened_pool[index])
                returned_labels.append(response.label)

            if attempted in budgets:
                checkpoint_model = _fit_surrogate(queried_images, returned_labels, seed)
                fidelity = None
                if checkpoint_model is not None:
                    predictions = checkpoint_model.predict(flattened_fidelity)
                    fidelity = float(np.mean(predictions == victim_fidelity_labels))
                points.append(
                    ExtractionPoint(attempted, len(returned_labels), fidelity)
                )

        if len(returned_labels) != fitted_response_count:
            surrogate = _fit_surrogate(queried_images, returned_labels, seed)
            fitted_response_count = len(returned_labels)

    return ExtractionResult(
        points=tuple(points),
        first_alert_query=first_alert,
        first_block_query=first_block,
        final_risk=final_risk,
        responses_received=len(returned_labels),
    )
