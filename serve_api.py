import argparse

import uvicorn

from modelsentry.api import create_app
from modelsentry.config import ExperimentConfig
from modelsentry.data import dataset_to_tensors, load_partitions
from modelsentry.experiment import build_benign_profile
from modelsentry.model import train_or_load_victim
from modelsentry.monitor import StatefulMonitor
from modelsentry.service import PredictionService
from modelsentry.store import EventStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the ModelSentry API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--disable-defence", action="store_true")
    args = parser.parse_args()

    config = ExperimentConfig()
    partitions = load_partitions(config)
    model, _ = train_or_load_victim(
        config, partitions.victim_train, partitions.victim_validation
    )
    calibration_images, _ = dataset_to_tensors(partitions.calibration)
    profile = build_benign_profile(model, calibration_images)
    store = EventStore(config.artifacts_dir / "api.db")
    service = PredictionService(
        model,
        StatefulMonitor(profile),
        store,
        defence_enabled=not args.disable_defence,
    )
    uvicorn.run(create_app(service), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
