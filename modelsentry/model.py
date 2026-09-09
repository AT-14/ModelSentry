import hashlib
import json

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .config import ExperimentConfig


class VictimCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.embedding = nn.Sequential(
            nn.Flatten(), nn.Linear(32 * 7 * 7, 64), nn.ReLU()
        )
        self.classifier = nn.Linear(64, 10)

    def forward(
        self, inputs: torch.Tensor, return_embedding: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        embedding = self.embedding(self.features(inputs))
        logits = self.classifier(embedding)
        if return_embedding:
            return logits, embedding
        return logits


def accuracy(model: nn.Module, dataset: Dataset, batch_size: int) -> float:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    device = next(model.parameters()).device
    correct = 0
    total = 0
    model.eval()
    with torch.inference_mode():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            predictions = model(images).argmax(dim=1)
            correct += int((predictions == labels).sum())
            total += labels.numel()
    return correct / total


def train_or_load_victim(
    config: ExperimentConfig, train: Dataset, validation: Dataset
) -> tuple[VictimCNN, float]:
    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = config.checkpoint_dir or config.artifacts_dir
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    profile_name = "quick" if config.quick else "full"
    stem = (
        f"victim_model_{profile_name}_seed{config.seed}"
        f"_e{config.epochs}_n{config.victim_train_size}"
    )
    checkpoint = checkpoint_dir / f"{stem}.pt"
    metadata_path = checkpoint_dir / f"{stem}.json"
    checksum_path = checkpoint_dir / f"{stem}.sha256"
    torch.manual_seed(config.seed)
    model = VictimCNN()

    if checkpoint.exists():
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        return model.eval(), accuracy(model, validation, config.batch_size)

    loader = DataLoader(
        train,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0,
        generator=torch.Generator().manual_seed(config.seed),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    criterion = nn.CrossEntropyLoss()
    print(f"  training device: {device}")

    model.train()
    for epoch in range(config.epochs):
        running_loss = 0.0
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.detach().item()
        print(f"  epoch {epoch + 1}/{config.epochs}, loss={running_loss / len(loader):.4f}")

    model.eval()
    validation_accuracy = accuracy(model, validation, config.batch_size)
    model.cpu()
    torch.save(model.state_dict(), checkpoint)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    metadata = {
        "architecture": "VictimCNN-2conv-64embedding",
        "dataset": "Fashion-MNIST",
        "input_shape": [1, 28, 28],
        "normalization": "ToTensor values in [0, 1]",
        "labels": [
            "T-shirt/top",
            "Trouser",
            "Pullover",
            "Dress",
            "Coat",
            "Sandal",
            "Shirt",
            "Sneaker",
            "Bag",
            "Ankle boot",
        ],
        "seed": config.seed,
        "profile": profile_name,
        "epochs": config.epochs,
        "validation_accuracy": validation_accuracy,
        "sha256": digest,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    checksum_path.write_text(f"{digest}  {checkpoint.name}\n", encoding="ascii")
    return model, validation_accuracy


def predict_batch(
    model: VictimCNN, images: torch.Tensor
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    device = next(model.parameters()).device
    with torch.inference_mode():
        logits, embeddings = model(images.to(device), return_embedding=True)
        probabilities = torch.softmax(logits, dim=1)
    return (
        probabilities.argmax(dim=1).cpu().numpy(),
        probabilities.cpu().numpy(),
        embeddings.cpu().numpy(),
    )
