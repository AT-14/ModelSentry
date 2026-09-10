import time
from collections.abc import Callable
from secrets import compare_digest
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


def create_app(
    service: PredictionService,
    *,
    reset_service: Callable[[], None] | None = None,
    demo_reset_token: str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="ModelSentry protected inference API",
        version="0.2.0",
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
                time.monotonic(),
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

    if reset_service is not None and demo_reset_token:

        @app.post("/demo/reset")
        def reset_demo(
            supplied_token: Annotated[str | None, Header(alias="X-Demo-Token")] = None,
        ) -> dict[str, str]:
            if supplied_token is None or not compare_digest(
                supplied_token, demo_reset_token
            ):
                raise HTTPException(status_code=403, detail="Invalid demo reset token")
            reset_service()
            return {"status": "reset"}

    return app
