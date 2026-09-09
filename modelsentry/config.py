from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExperimentConfig:
    seed: int = 42
    quick: bool = True
    batch_size: int = 64
    epochs: int = 3
    learning_rate: float = 1e-3
    victim_train_size: int = 8_000
    victim_validation_size: int = 1_000
    calibration_size: int = 1_000
    attack_pool_size: int = 3_000
    benign_evaluation_size: int = 2_000
    fidelity_evaluation_size: int = 5_000
    query_budgets: tuple[int, ...] = (100, 250, 500, 1_000)
    data_dir: Path = Path("data")
    artifacts_dir: Path = Path("artifacts")
    checkpoint_dir: Path | None = None

    @classmethod
    def full(cls, seed: int = 42) -> "ExperimentConfig":
        return cls(
            seed=seed,
            quick=False,
            epochs=6,
            victim_train_size=40_000,
            victim_validation_size=5_000,
            calibration_size=5_000,
            attack_pool_size=5_000,
            benign_evaluation_size=5_000,
            fidelity_evaluation_size=5_000,
            query_budgets=(100, 250, 500, 1_000, 2_000, 5_000),
        )
