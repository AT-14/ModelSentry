import argparse
import hashlib
import json
import random
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from modelsentry.config import ExperimentConfig
from modelsentry.data import dataset_to_tensors, load_partitions
from modelsentry.model import predict_batch, train_or_load_victim
from modelsentry.validation_v2 import (
    ATTACK_SCENARIOS,
    ALL_MODES,
    BENIGN_PROFILES,
    ENHANCED_POLICY,
    run_extended_experiment,
)


ROOT = Path(__file__).resolve().parent
PROTECTED_EVIDENCE = (ROOT / "artifacts" / "validation_corrected").resolve()


def validate_output_path(output: Path) -> Path:
    resolved = (ROOT / output).resolve() if not output.is_absolute() else output.resolve()
    if resolved == PROTECTED_EVIDENCE or PROTECTED_EVIDENCE in resolved.parents:
        raise ValueError("Extended V2 cannot write to Baseline V1 corrected evidence")
    return resolved


def mean_std(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
    }


def protocol_signature(
    seed: int,
    config: ExperimentConfig,
    modes: tuple[str, ...] = ALL_MODES,
) -> str:
    protocol = {
        "schema_version": 2,
        "seed": seed,
        "quick": config.quick,
        "epochs": config.epochs,
        "victim_train_size": config.victim_train_size,
        "calibration_size": config.calibration_size,
        "attack_pool_size": config.attack_pool_size,
        "benign_evaluation_size": config.benign_evaluation_size,
        "fidelity_evaluation_size": config.fidelity_evaluation_size,
        "query_budgets": config.query_budgets,
        "benign_profiles": [asdict(profile) for profile in BENIGN_PROFILES],
        "attack_scenarios": [asdict(scenario) for scenario in ATTACK_SCENARIOS],
        "enhanced_policy": ENHANCED_POLICY,
        "detector_modes": modes,
    }
    encoded = json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_manifest(
    output: Path,
    seeds: list[int],
    quick: bool,
    signatures: dict[int, str],
) -> None:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest_v2.json")
    manifest = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": "quick" if quick else "full",
        "seeds": seeds,
        "protocol_signatures": signatures,
        "protected_baseline": str(PROTECTED_EVIDENCE),
        "source_revision": (
            revision.stdout.strip() if revision.returncode == 0 else "unavailable"
        ),
        "source_dirty": status.returncode != 0 or bool(status.stdout.strip()),
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
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Optional local smoke cap; full V2 runs should use the defaults",
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/validation_extended_v2"))
    parser.add_argument(
        "--checkpoint-source",
        type=Path,
        default=None,
        help="Optional directory containing seed_<n> checkpoint folders",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a seed only when its V2 protocol signature matches",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=ALL_MODES,
        default=list(ALL_MODES),
        help="Detector modes to evaluate; defaults to all modes",
    )
    args = parser.parse_args()
    output = validate_output_path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    benign_rows: list[dict] = []
    latency_rows: list[dict] = []
    signatures: dict[int, str] = {}

    for seed in args.seeds:
        base = ExperimentConfig(seed=seed) if args.quick else ExperimentConfig.full(seed)
        if args.quick:
            # V2 needs long benign sessions to exercise long-horizon rules even
            # when victim training and attack budgets use local smoke settings.
            base = replace(base, benign_evaluation_size=5_000)
        query_budgets = base.query_budgets
        if args.max_queries is not None:
            if args.max_queries < min(base.query_budgets):
                raise ValueError(
                    f"max queries must be at least {min(base.query_budgets)}"
                )
            query_budgets = tuple(
                budget for budget in base.query_budgets if budget <= args.max_queries
            )
            if args.max_queries not in query_budgets:
                query_budgets += (args.max_queries,)
        config = replace(
            base,
            epochs=args.epochs if args.epochs is not None else base.epochs,
            query_budgets=query_budgets,
            artifacts_dir=output / f"seed_{seed}",
            checkpoint_dir=(
                args.checkpoint_source / f"seed_{seed}"
                if args.checkpoint_source is not None
                else None
            ),
        )
        modes = tuple(args.modes)
        signature = protocol_signature(seed, config, modes)
        signatures[seed] = signature
        result_path = config.artifacts_dir / "results_v2.json"
        if args.resume and result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("protocol_signature") != signature:
                raise ValueError(
                    f"Cannot resume seed {seed}: saved V2 protocol does not match"
                )
            print(f"Reusing matching V2 result: {result_path}")
        else:
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            partitions = load_partitions(config)
            model, accuracy = train_or_load_victim(
                config, partitions.victim_train, partitions.victim_validation
            )
            model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
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
                modes=modes,
            )
            model.cpu()
            result["victim_validation_accuracy"] = accuracy
            result["protocol_signature"] = signature
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        accuracy = result["victim_validation_accuracy"]
        for mode, mode_result in result["detector_modes"].items():
            benign = mode_result["benign_sessions"]
            benign_flagged = sum(item["first_alert_query"] is not None for item in benign)
            for session in benign:
                benign_rows.append({"seed": seed, **session})
            for scenario, attack in mode_result["attacks"].items():
                rows.append(
                    {
                        "seed": seed,
                        "mode": mode,
                        "scenario": scenario,
                        "victim_validation_accuracy": accuracy,
                        "first_alert_query": attack["first_alert_query"],
                        "answered_queries_at_first_alert": attack["answered_queries_at_first_alert"],
                        "fidelity_at_first_alert": attack["fidelity_at_first_alert"],
                        "final_fidelity": attack["points"][-1]["fidelity"],
                        "responses_received": attack["responses_received"],
                        "maximum_queries": attack["maximum_queries"],
                        "benign_sessions_flagged": benign_flagged,
                        "benign_sessions_tested": len(benign),
                    }
                )
            for layer, latency in mode_result.get("latency", {}).items():
                latency_rows.append({"seed": seed, "mode": mode, "layer": layer, **latency})

    frame = pd.DataFrame(rows)
    frame.to_csv(output / "per_mode_metrics_v2.csv", index=False)
    benign_frame = pd.DataFrame(benign_rows)
    latency_frame = pd.DataFrame(latency_rows)
    benign_frame.to_csv(output / "benign_sessions_v2.csv", index=False)
    latency_frame.to_csv(output / "latency_v2.csv", index=False)
    latency_summary = (
        {
            f"{mode}/{layer}": {
                "p50_ms": mean_std(group["p50_ms"].tolist()),
                "p95_ms": mean_std(group["p95_ms"].tolist()),
            }
            for (mode, layer), group in latency_frame.groupby(["mode", "layer"])
        }
        if not latency_frame.empty
        else {}
    )
    summary = {
        "schema_version": 2,
        "seeds": args.seeds,
        "profile": "quick" if args.quick else "full",
        "protocol_signatures": signatures,
        "mode_overview": {
            mode: {
                "attack_detection_rate": float(
                    group["first_alert_query"].notna().mean()
                ),
                "attack_runs_detected": int(group["first_alert_query"].notna().sum()),
                "attack_runs_tested": len(group),
                "benign_false_positive_rate": float(
                    benign_frame.loc[benign_frame["mode"] == mode, "first_alert_query"]
                    .notna()
                    .mean()
                ),
                "benign_sessions_mitigated": int(
                    benign_frame.loc[benign_frame["mode"] == mode, "first_alert_query"]
                    .notna()
                    .sum()
                ),
                "benign_sessions_tested": int((benign_frame["mode"] == mode).sum()),
                "final_fidelity": mean_std(group["final_fidelity"].dropna().tolist()),
            }
            for mode, group in frame.groupby("mode")
        },
        "latency": latency_summary,
        "results": {
            f"{mode}/{scenario}": {
                "attack_detection_rate": float(group["first_alert_query"].notna().mean()),
                "benign_false_positive_rate": float(
                    group.drop_duplicates("seed")["benign_sessions_flagged"].sum()
                    / group.drop_duplicates("seed")["benign_sessions_tested"].sum()
                ),
                "first_alert_query": mean_std(group["first_alert_query"].dropna().tolist()),
                "fidelity_at_first_alert": mean_std(group["fidelity_at_first_alert"].dropna().tolist()),
                "final_fidelity": mean_std(group["final_fidelity"].dropna().tolist()),
            }
            for (mode, scenario), group in frame.groupby(["mode", "scenario"])
        },
    }
    (output / "validation_summary_v2.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_manifest(output, args.seeds, args.quick, signatures)
    print(json.dumps(summary, indent=2))
    print(f"Extended V2 outputs: {output}")


if __name__ == "__main__":
    main()
