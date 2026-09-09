import argparse
import hashlib
import json
import random
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from modelsentry.config import ExperimentConfig
from modelsentry.data import load_partitions
from modelsentry.experiment import run_experiment
from modelsentry.model import train_or_load_victim


def _point_map(result: dict) -> dict[int, float | None]:
    return {point["attempted_queries"]: point["fidelity"] for point in result["points"]}


def _mean_std(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
    }


def _save_validation_chart(seed_results: list[dict], destination: Path) -> None:
    budgets = sorted(
        {
            point["attempted_queries"]
            for result in seed_results
            for point in result["undefended_attack"]["points"]
        }
    )
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for result_key, label, color in (
        ("undefended_attack", "Defence disabled", "#c43d3d"),
        ("defended_attack", "ModelSentry enabled", "#147d64"),
    ):
        curves = []
        for result in seed_results:
            points = _point_map(result[result_key])
            curves.append([points.get(budget, np.nan) for budget in budgets])
        values = np.asarray(curves, dtype=np.float64)
        means = np.nanmean(values, axis=0)
        stds = np.nanstd(values, axis=0, ddof=1) if len(curves) > 1 else np.zeros(len(budgets))
        axis.plot(budgets, means, marker="o", linewidth=2.5, label=label, color=color)
        axis.fill_between(budgets, means - stds, means + stds, color=color, alpha=0.18)
    axis.set_xlabel("Attempted API queries")
    axis.set_ylabel("Mean surrogate-to-victim fidelity")
    axis.set_ylim(0, 1)
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    figure.savefig(destination, dpi=220)
    plt.close(figure)


def _write_manifest(output_dir: Path, seeds: list[int], quick: bool) -> None:
    files = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.name != "manifest.json"
        and path.suffix.lower() in {".json", ".csv", ".png", ".sha256"}
    )
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": "quick" if quick else "full",
        "seeds": seeds,
        "files": {
            str(path.relative_to(output_dir)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in files
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-seed ModelSentry validation")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 7, 123])
    parser.add_argument("--quick", action="store_true", help="Use local CPU-friendly settings")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("artifacts/validation"))
    parser.add_argument(
        "--checkpoint-source",
        type=Path,
        default=None,
        help="Optional directory containing seed_<n> checkpoint folders",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed seed results in the output directory",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    all_results: list[dict] = []
    rows: list[dict] = []
    effective_epochs: list[int] = []

    for run_number, seed in enumerate(args.seeds, start=1):
        print(f"\n=== Validation run {run_number}/{len(args.seeds)}: seed {seed} ===")
        base = ExperimentConfig(seed=seed) if args.quick else ExperimentConfig.full(seed)
        epochs = args.epochs if args.epochs is not None else base.epochs
        effective_epochs.append(epochs)
        config = replace(
            base,
            epochs=epochs,
            artifacts_dir=args.output / f"seed_{seed}",
            checkpoint_dir=(
                args.checkpoint_source / f"seed_{seed}"
                if args.checkpoint_source is not None
                else None
            ),
        )
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

        partitions = load_partitions(config)
        model, validation_accuracy = train_or_load_victim(
            config, partitions.victim_train, partitions.victim_validation
        )
        result_path = config.artifacts_dir / "results.json"
        if args.resume and result_path.exists():
            print(f"  reusing completed result: {result_path}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            result = run_experiment(config, model, partitions)
        result["victim_validation_accuracy"] = validation_accuracy
        all_results.append(result)

        summary = result["summary"]
        defended = result["defended_attack"]
        slow_attack = result["slow_attack"]
        rate_only = result["rate_only_baseline"]
        rows.append(
            {
                "seed": seed,
                "victim_validation_accuracy": validation_accuracy,
                "attack_detected": bool(summary["attack_detected"]),
                "first_alert_query": defended["first_alert_query"],
                "first_alert_seconds": (
                    defended["first_alert_query"] * 0.01
                    if defended["first_alert_query"] is not None
                    else np.nan
                ),
                "slow_attack_detected": slow_attack["first_alert_query"] is not None,
                "slow_first_alert_query": slow_attack["first_alert_query"],
                "rate_only_fast_detected": rate_only["fast_attack_detected"],
                "rate_only_slow_detected": rate_only["slow_attack_detected"],
                "rate_only_benign_flagged": rate_only["benign_clients_flagged"],
                "benign_clients_blocked": summary["benign_clients_blocked"],
                "benign_clients_tested": summary["benign_clients_tested"],
                "responses_prevented": summary["responses_prevented"],
                "undefended_final_fidelity": summary["undefended_final_fidelity"],
                "defended_final_fidelity": summary["defended_final_fidelity"],
                "fidelity_reduction": summary["undefended_final_fidelity"]
                - summary["defended_final_fidelity"],
            }
        )

    frame = pd.DataFrame(rows)
    frame.to_csv(args.output / "per_seed_metrics.csv", index=False)
    detected_alerts = frame.loc[frame["attack_detected"], "first_alert_query"].dropna().tolist()
    summary = {
        "profile": "quick" if args.quick else "full",
        "seeds": args.seeds,
        "epochs": sorted(set(effective_epochs)),
        "victim_train_size": (
            ExperimentConfig().victim_train_size
            if args.quick
            else ExperimentConfig.full().victim_train_size
        ),
        "runs": len(frame),
        "detection_rate": float(frame["attack_detected"].mean()),
        "slow_attack_detection_rate": float(frame["slow_attack_detected"].mean()),
        "rate_only_fast_detection_rate": float(frame["rate_only_fast_detected"].mean()),
        "rate_only_slow_detection_rate": float(frame["rate_only_slow_detected"].mean()),
        "rate_only_benign_false_positive_rate": float(
            frame["rate_only_benign_flagged"].sum()
            / frame["benign_clients_tested"].sum()
        ),
        "benign_false_positive_rate": float(
            frame["benign_clients_blocked"].sum()
            / frame["benign_clients_tested"].sum()
        ),
        "victim_validation_accuracy": _mean_std(
            frame["victim_validation_accuracy"].tolist()
        ),
        "undefended_final_fidelity": _mean_std(
            frame["undefended_final_fidelity"].tolist()
        ),
        "defended_final_fidelity": _mean_std(
            frame["defended_final_fidelity"].tolist()
        ),
        "fidelity_reduction": _mean_std(frame["fidelity_reduction"].tolist()),
        "responses_prevented": _mean_std(frame["responses_prevented"].tolist()),
        "first_alert_query": _mean_std(detected_alerts) if detected_alerts else None,
    }
    (args.output / "validation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    _save_validation_chart(all_results, args.output / "multi_seed_fidelity.png")
    _write_manifest(args.output, args.seeds, args.quick)

    print("\n=== Aggregate validation ===")
    print(json.dumps(summary, indent=2))
    print(f"Frozen outputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
