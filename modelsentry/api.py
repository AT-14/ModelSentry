import time
from typing import Annotated

import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .service import PredictionService


class PredictionRequest(BaseModel):
    pixels: list[float] = Field(
        min_length=28 * 28,
        max_length=28 * 28,
        description="Flattened 28x28 grayscale image with values in [0, 1]",
    )


class PredictionOutput(BaseModel):
    allowed: bool
    label: int | None
    probabilities: list[float] | None
    risk: float
    action: str
    reasons: list[str]


def create_app(service: PredictionService) -> FastAPI:
    app = FastAPI(
        title="ModelSentry protected inference API",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/predict", response_model=PredictionOutput)
    def predict(
        payload: PredictionRequest,
        api_key: Annotated[str, Header(alias="X-API-Key")],
    ) -> PredictionOutput:
        try:
            image = torch.from_numpy(
                np.asarray(payload.pixels, dtype=np.float32).reshape(1, 28, 28)
            )
            response = service.predict(
                api_key,
                image,
                # Public clients must not control timestamps used by rate detection.
                time.time(),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        probabilities = (
            response.probabilities.tolist()
            if response.probabilities is not None
            else None
        )
        return PredictionOutput(
            allowed=response.allowed,
            label=response.label,
            probabilities=probabilities,
            risk=response.assessment.risk,
            action=response.assessment.action,
            reasons=list(response.assessment.reasons),
        )

    return app
