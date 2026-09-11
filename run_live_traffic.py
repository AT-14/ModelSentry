import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import torch
from torch.utils.data import Dataset

from modelsentry.config import ExperimentConfig
from modelsentry.data import load_partitions


ROOT = Path(__file__).resolve().parent
MITIGATION_ACTIONS = {"throttle", "block"}


@dataclass(frozen=True)
class LiveAttackResult:
    queries: int
    elapsed_seconds: float
    action: str
    risk: float
    reasons: tuple[str, ...]


def dataset_images(dataset: Dataset, count: int) -> torch.Tensor:
    return torch.stack([dataset[index][0] for index in range(count)])


def predict(client: httpx.Client, api_key: str, image: torch.Tensor) -> dict:
    response = client.post(
        "/predict",
        headers={"X-API-Key": api_key},
        json={"pixels": image.reshape(-1).tolist()},
    )
    response.raise_for_status()
    return response.json()


def reset_demo(client: httpx.Client, token: str) -> None:
    response = client.post("/demo/reset", headers={"X-Demo-Token": token})
    response.raise_for_status()
    print("Demo state reset. Dashboard is ready and green.")


def run_normal_phase(
    client: httpx.Client,
    images: torch.Tensor,
    delay_seconds: float,
) -> None:
    print(f"Starting normal traffic: {len(images)} unique requests")
    for index, image in enumerate(images, start=1):
        result = predict(client, "normal-client", image)
        if result["action"] in MITIGATION_ACTIONS or not result["allowed"]:
            raise RuntimeError(
                f"Normal traffic was mitigated at request {index}: {result}"
            )
        if index % 25 == 0 or index == len(images):
            print(f"  Normal request {index}/{len(images)}: {result['action']}")
        if delay_seconds:
            time.sleep(delay_seconds)
    print("Normal traffic completed with no throttle or block. Dashboard stays green.")


def run_attack_phase(
    client: httpx.Client,
    pool: torch.Tensor,
    maximum_queries: int,
    delay_seconds: float = 0.0,
) -> LiveAttackResult:
    print(
        "Starting extraction traffic: repeated diverse pool, maximum "
        f"{maximum_queries} requests"
    )
    started = time.perf_counter()
    for query in range(1, maximum_queries + 1):
        result = predict(client, "extractor-client", pool[(query - 1) % len(pool)])
        if query % 25 == 0:
            print(f"  Extraction request {query}: {result['action']}")
        if result["action"] in MITIGATION_ACTIONS:
            elapsed = time.perf_counter() - started
            outcome = LiveAttackResult(
                queries=query,
                elapsed_seconds=elapsed,
                action=result["action"],
                risk=float(result["risk"]),
                reasons=tuple(result["reasons"]),
            )
            print(
                f"ALERT: {outcome.action.upper()} at query {outcome.queries} "
                f"after {outcome.elapsed_seconds:.2f} real seconds"
            )
            print("Trigger: " + "; ".join(outcome.reasons))
            return outcome
        if delay_seconds:
            time.sleep(delay_seconds)
    raise RuntimeError(f"No extraction alert within {maximum_queries} requests")


def check_unexpected_input(client: httpx.Client) -> None:
    malformed = client.post(
        "/predict",
        headers={"X-API-Key": "invalid-input-check"},
        json={"pixels": [0.0] * 783},
    )
    if malformed.status_code != 422:
        raise RuntimeError(f"Expected HTTP 422, received {malformed.status_code}")
    health = client.get("/health")
    health.raise_for_status()
    print("Unexpected-input check: HTTP 422 returned; API remains healthy.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drive the live ModelSentry API with normal and extraction traffic"
    )
    parser.add_argument(
        "phase", choices=("reset", "normal", "attack", "invalid", "all")
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--demo-token", default="modelsentry-demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--normal-requests", type=int, default=75)
    parser.add_argument("--normal-delay", type=float, default=0.05)
    parser.add_argument("--attack-pool-size", type=int, default=50)
    parser.add_argument("--max-attack-queries", type=int, default=150)
    parser.add_argument("--attack-delay", type=float, default=0.0)
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=20.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print(f"API health: {health.json()['status']}")

        if args.phase in {"reset", "all"}:
            reset_demo(client, args.demo_token)
        if args.phase in {"normal", "attack", "all"}:
            config = ExperimentConfig(
                seed=args.seed,
                data_dir=ROOT / "data",
                artifacts_dir=ROOT / "artifacts",
            )
            partitions = load_partitions(config)
            if args.phase in {"normal", "all"}:
                normal_images = dataset_images(
                    partitions.benign_evaluation, args.normal_requests
                )
                run_normal_phase(client, normal_images, args.normal_delay)
            if args.phase in {"attack", "all"}:
                attack_pool = dataset_images(
                    partitions.attack_pool, args.attack_pool_size
                )
                run_attack_phase(
                    client,
                    attack_pool,
                    args.max_attack_queries,
                    args.attack_delay,
                )
        if args.phase in {"invalid", "all"}:
            check_unexpected_input(client)


if __name__ == "__main__":
    main()
