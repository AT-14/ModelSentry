import argparse
import random

import numpy as np
import torch

from modelsentry.config import ExperimentConfig
from modelsentry.data import load_partitions
from modelsentry.experiment import run_experiment
from modelsentry.model import train_or_load_victim


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ModelSentry experiment")
    parser.add_argument("--quick", action="store_true", help="Use the CPU-friendly profile")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = ExperimentConfig(seed=args.seed) if args.quick else ExperimentConfig.full(args.seed)
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)

    print("[1/5] Loading disjoint Fashion-MNIST partitions...")
    partitions = load_partitions(config)
    print("[2/5] Training or loading the protected model...")
    model, validation_accuracy = train_or_load_victim(
        config, partitions.victim_train, partitions.victim_validation
    )
    print(f"Protected-model validation accuracy: {validation_accuracy:.3f}")
    print("[3/5] Calibrating on benign traffic and running client profiles...")
    print("[4/5] Running undefended and defended extraction attacks...")
    results = run_experiment(config, model, partitions)
    print("[5/5] Results and chart written to artifacts/.")
    undefended = results["undefended_attack"]
    defended = results["defended_attack"]
    print(f"Normal max risk: {results['normal_client']['max_risk']:.3f}")
    print(f"Batch max risk: {results['batch_client']['max_risk']:.3f}")
    print(f"Attack first alert: {defended['first_alert_query']}")
    print(
        "Responses received (undefended/defended): "
        f"{undefended['responses_received']}/{defended['responses_received']}"
    )
    print(
        "Slow attack detected: "
        f"{results['summary']['slow_attack_detected']} "
        "(expected residual limitation in the current prototype)"
    )


if __name__ == "__main__":
    main()
