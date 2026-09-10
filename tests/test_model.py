import hashlib
from pathlib import Path

import pytest
import torch
from torch.utils.data import TensorDataset

from modelsentry.config import ExperimentConfig
from modelsentry.model import VictimCNN, train_or_load_victim


def tiny_dataset() -> TensorDataset:
    return TensorDataset(torch.zeros(2, 1, 28, 28), torch.zeros(2, dtype=torch.long))


def checkpoint_paths(root: Path) -> tuple[Path, Path]:
    stem = "victim_model_quick_seed42_e3_n8000"
    return root / f"{stem}.pt", root / f"{stem}.sha256"


def test_checkpoint_checksum_is_verified(tmp_path: Path) -> None:
    checkpoint, checksum = checkpoint_paths(tmp_path)
    torch.save(VictimCNN().state_dict(), checkpoint)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {checkpoint.name}\n", encoding="ascii")
    config = ExperimentConfig(artifacts_dir=tmp_path)

    model, validation_accuracy = train_or_load_victim(
        config, tiny_dataset(), tiny_dataset(), require_checkpoint=True
    )

    assert isinstance(model, VictimCNN)
    assert 0.0 <= validation_accuracy <= 1.0


def test_corrupt_checkpoint_is_rejected_before_loading(tmp_path: Path) -> None:
    checkpoint, checksum = checkpoint_paths(tmp_path)
    checkpoint.write_bytes(b"corrupt checkpoint")
    checksum.write_text(f"{'0' * 64}  {checkpoint.name}\n", encoding="ascii")
    config = ExperimentConfig(artifacts_dir=tmp_path)

    with pytest.raises(ValueError, match="checksum mismatch"):
        train_or_load_victim(
            config, tiny_dataset(), tiny_dataset(), require_checkpoint=True
        )


def test_required_checkpoint_requires_checksum(tmp_path: Path) -> None:
    checkpoint, _ = checkpoint_paths(tmp_path)
    torch.save(VictimCNN().state_dict(), checkpoint)
    config = ExperimentConfig(artifacts_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="checkpoint checksum is missing"):
        train_or_load_victim(
            config, tiny_dataset(), tiny_dataset(), require_checkpoint=True
        )


def test_required_checkpoint_prevents_training_during_demo(tmp_path: Path) -> None:
    config = ExperimentConfig(artifacts_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="Required checkpoint is missing"):
        train_or_load_victim(
            config, tiny_dataset(), tiny_dataset(), require_checkpoint=True
        )
