from pydantic import BaseModel


class ApiEnvelope[T](BaseModel):
    code: int
    internal_code: str
    message: str
    data: T | None


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str


class ErrorEnvelope[Status: int, InternalCode: str](BaseModel):
    code: Status
    internal_code: InternalCode
    message: str
    data: ErrorDetail
