from typing import Any, Literal
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from risk_api.shared.api.envelope import ApiEnvelope, ErrorDetail, ErrorEnvelope

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorEnvelope[Literal[403], Literal["REQUEST_ORIGIN_INVALID"]]},
    422: {"model": ErrorEnvelope[Literal[422], Literal["REQUEST_INVALID"]]},
    500: {"model": ErrorEnvelope[Literal[500], Literal["INTERNAL_ERROR"]]},
}


def success[T](data: T, *, message: str = "OK") -> ApiEnvelope[T]:
    return ApiEnvelope(code=200, internal_code="SUCCESS", message=message, data=data)


def error_response(
    request: Request, *, status: int, internal_code: str, message: str, field: str | None = None
) -> JSONResponse:
    request.state.internal_code = internal_code
    payload = ApiEnvelope[ErrorDetail](
        code=status,
        internal_code=internal_code,
        message=message,
        data=ErrorDetail(field=field, reason=message),
    )
    return JSONResponse(
        status_code=status,
        headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid4()))},
        content=payload.model_dump(),
    )
