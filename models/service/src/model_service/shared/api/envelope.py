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
    ]
    message: str
    data: ErrorDetail
