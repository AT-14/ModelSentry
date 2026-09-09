from dataclasses import dataclass

import torch
from torch.utils.data import Dataset, Subset
from torchvision import datasets, transforms

from .config import ExperimentConfig


@dataclass(frozen=True)
class DataPartitions:
    victim_train: Dataset
    victim_validation: Dataset
    calibration: Dataset
    attack_pool: Dataset
    benign_evaluation: Dataset
    fidelity_evaluation: Dataset


def load_partitions(config: ExperimentConfig) -> DataPartitions:
    transform = transforms.ToTensor()
    train = datasets.FashionMNIST(
        root=config.data_dir, train=True, download=True, transform=transform
    )
    test = datasets.FashionMNIST(
        root=config.data_dir, train=False, download=True, transform=transform
    )

    generator = torch.Generator().manual_seed(config.seed)
    train_indices = torch.randperm(len(train), generator=generator).tolist()
    test_indices = torch.randperm(len(test), generator=generator).tolist()

    cursor = 0

    def take_train(size: int) -> Subset:
        nonlocal cursor
        result = Subset(train, train_indices[cursor : cursor + size])
        cursor += size
        return result

    victim_train = take_train(config.victim_train_size)
    victim_validation = take_train(config.victim_validation_size)
    calibration = take_train(config.calibration_size)
    attack_pool = take_train(config.attack_pool_size)

    benign_end = config.benign_evaluation_size
    fidelity_end = benign_end + config.fidelity_evaluation_size
    if fidelity_end > len(test):
        raise ValueError("Requested evaluation partitions exceed the test set")

    return DataPartitions(
        victim_train=victim_train,
        victim_validation=victim_validation,
        calibration=calibration,
        attack_pool=attack_pool,
        benign_evaluation=Subset(test, test_indices[:benign_end]),
        fidelity_evaluation=Subset(test, test_indices[benign_end:fidelity_end]),
    )


def dataset_to_tensors(dataset: Dataset) -> tuple[torch.Tensor, torch.Tensor]:
    images: list[torch.Tensor] = []
    labels: list[int] = []
    for image, label in dataset:
        images.append(image)
        labels.append(int(label))
    return torch.stack(images), torch.tensor(labels, dtype=torch.long)
