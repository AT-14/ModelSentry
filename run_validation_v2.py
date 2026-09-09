import argparse
import hashlib
import json
import random
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from modelsentry.config import ExperimentConfig
from modelsentry.data import dataset_to_tensors, load_partitions
from modelsentry.model import predict_batch, train_or_load_victim
from modelsentry.validation_v2 import run_extended_experiment


ROOT = Path(__file__).resolve().parent
PROTECTED_EVIDENCE = (ROOT / "artifacts" / "validation_corrected").resolve()


def validate_output_path(output: Path) -> Path:
    resolved = (ROOT / output).resolve() if not output.is_absolute() else output.resolve()
    if resolved == PROTECTED_EVIDENCE or PROTECTED_EVIDENCE in resolved.parents:
        raise ValueError("Extended V2 cannot write to Baseline V1 corrected evidence")
    return resolved


def mean_std(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
    }


def write_manifest(output: Path, seeds: list[int], quick: bool) -> None:
    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest_v2.json")
    manifest = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": "quick" if quick else "full",
        "seeds": seeds,
        "protected_baseline": str(PROTECTED_EVIDENCE),
        "files": {
            str(path.relative_to(output)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    (output / "manifest_v2.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated ModelSentry Extended V2 validation")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 7, 123])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("artifacts/validation_extended_v2"))
    args = parser.parse_args()
    output = validate_output_path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for seed in args.seeds:
        base = ExperimentConfig(seed=seed) if args.quick else ExperimentConfig.full(seed)
        config = replace(
            base,
            epochs=args.epochs if args.epochs is not None else base.epochs,
            artifacts_dir=output / f"seed_{seed}",
        )
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        partitions = load_partitions(config)
        model, accuracy = train_or_load_victim(
            config, partitions.victim_train, partitions.victim_validation
        )
        calibration_images, _ = dataset_to_tensors(partitions.calibration)
        benign_images, _ = dataset_to_tensors(partitions.benign_evaluation)
        attack_images, _ = dataset_to_tensors(partitions.attack_pool)
        fidelity_images, _ = dataset_to_tensors(partitions.fidelity_evaluation)
        victim_labels, _, _ = predict_batch(model, fidelity_images)
        result = run_extended_experiment(
            model,
            calibration_images,
            benign_images,
            attack_images,
            fidelity_images,
            victim_labels,
            config.query_budgets,
            seed,
            config.artifacts_dir,
        )
        result["victim_validation_accuracy"] = accuracy
        (config.artifacts_dir / "results_v2.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        for mode, mode_result in result["detector_modes"].items():
            attack = mode_result["fast_attack"]
            benign = mode_result["benign_sessions"]
            rows.append(
                {
                    "seed": seed,
                    "mode": mode,
                    "victim_validation_accuracy": accuracy,
                    "first_alert_query": attack["first_alert_query"],
                    "fidelity_at_first_alert": attack["fidelity_at_first_alert"],
                    "final_fidelity": attack["points"][-1]["fidelity"],
                    "responses_received": attack["responses_received"],
                    "benign_sessions_flagged": sum(item["first_alert_query"] is not None for item in benign),
                    "benign_sessions_tested": len(benign),
                }
            )

    frame = pd.DataFrame(rows)
    frame.to_csv(output / "per_mode_metrics_v2.csv", index=False)
    summary = {
        "schema_version": 2,
        "seeds": args.seeds,
        "modes": {
            mode: {
                "attack_detection_rate": float(group["first_alert_query"].notna().mean()),
                "benign_false_positive_rate": float(group["benign_sessions_flagged"].sum() / group["benign_sessions_tested"].sum()),
                "final_fidelity": mean_std(group["final_fidelity"].dropna().tolist()),
            }
            for mode, group in frame.groupby("mode")
        },
    }
    (output / "validation_summary_v2.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_manifest(output, args.seeds, args.quick)
    print(json.dumps(summary, indent=2))
    print(f"Extended V2 outputs: {output}")


if __name__ == "__main__":
    main()
