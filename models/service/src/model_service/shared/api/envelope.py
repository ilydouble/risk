from typing import Literal

from pydantic import BaseModel


class Envelope[T](BaseModel):
    code: int = 200
    internal_code: str = "SUCCESS"
    message: str = "OK"
    data: T


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str


class ErrorEnvelope(BaseModel):
    code: int
    internal_code: Literal[
        "SERVICE_UNAUTHORIZED",
        "REQUEST_INVALID",
        "MODEL_STATE_INVALID",
        "MODEL_RESOURCE_NOT_FOUND",
        "MODEL_SERVICE_UNAVAILABLE",
        "ROUTE_NOT_FOUND",
        "DECISION_MODEL_DISABLED",
        "DECISION_MODEL_UNAVAILABLE",
        "DECISION_INPUT_INVALID",
        "DECISION_DATASET_UNSUPPORTED",
        "DECISION_VERSION_CHANGED",
        "DECISION_BUSY",
        "DECISION_TIMEOUT",
        "DECISION_PREDICTION_FAILED",
    ]
    message: str
    data: ErrorDetail
