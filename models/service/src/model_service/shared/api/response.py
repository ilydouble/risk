from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from model_service.shared.api.envelope import Envelope, ErrorEnvelope

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorEnvelope} for status in (401, 404, 409, 422, 503)
}


def success_response[T](data: T) -> Envelope[T]:
    return Envelope(data=data)


def error_response(
    request: Request, status: int, code: str, message: str, *, field: str | None = None
) -> JSONResponse:
    return JSONResponse(
        {
            "code": status,
            "internal_code": code,
            "message": message,
            "data": {"field": field, "reason": message},
        },
        status_code=status,
        headers={"X-Request-ID": request.state.request_id},
    )
