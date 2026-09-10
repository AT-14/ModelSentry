import argparse
from pathlib import Path

import uvicorn

from modelsentry.api import create_app
from modelsentry.config import ExperimentConfig
from modelsentry.data import dataset_to_tensors, load_partitions
from modelsentry.experiment import build_benign_profile
from modelsentry.model import train_or_load_victim
from modelsentry.monitor import StatefulMonitor
from modelsentry.service import PredictionService
from modelsentry.store import EventStore
from modelsentry.validation_v2 import EnhancedMonitor, build_extended_benign_profile


ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the ModelSentry API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--monitor", choices=("baseline", "enhanced"), default="enhanced"
    )
    parser.add_argument(
        "--database", type=Path, default=ROOT / "artifacts" / "live_demo.db"
    )
    parser.add_argument("--reset-db", action="store_true")
    parser.add_argument("--demo-reset-token")
    parser.add_argument("--access-log", action="store_true")
    parser.add_argument("--require-checkpoint", action="store_true")
    parser.add_argument("--disable-defence", action="store_true")
    args = parser.parse_args()
    if args.demo_reset_token is not None:
        if not args.demo_reset_token:
            raise ValueError("The demo reset token must not be empty")
        if args.host not in {"127.0.0.1", "localhost"}:
            raise ValueError("The demo reset endpoint may only bind to a loopback host")

    config = ExperimentConfig(
        seed=args.seed,
        data_dir=ROOT / "data",
        artifacts_dir=ROOT / "artifacts",
    )
    partitions = load_partitions(config)
    model, _ = train_or_load_victim(
        config,
        partitions.victim_train,
        partitions.victim_validation,
        require_checkpoint=args.require_checkpoint,
    )
    calibration_images, _ = dataset_to_tensors(partitions.calibration)
    profile = (
        build_extended_benign_profile(model, calibration_images)
        if args.monitor == "enhanced"
        else build_benign_profile(model, calibration_images)
    )

    def new_monitor():
        return (
            EnhancedMonitor(profile)
            if args.monitor == "enhanced"
            else StatefulMonitor(profile)
        )

    database = args.database if args.database.is_absolute() else ROOT / args.database
    store = EventStore(database)
    if args.reset_db:
        store.reset()
    service = PredictionService(
        model,
        new_monitor(),
        store,
        defence_enabled=not args.disable_defence,
    )
    app = create_app(
        service,
        reset_service=lambda: service.reset(new_monitor()),
        demo_reset_token=args.demo_reset_token,
    )
    print(f"Monitor: {args.monitor}; event database: {database}", flush=True)
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            workers=1,
            access_log=args.access_log,
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
