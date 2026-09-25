import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from risk_api.schemas import ApiEnvelope, ErrorDetail

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.field = field


def error_response(request: Request, error: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    payload = ApiEnvelope[ErrorDetail](
        code=error.status,
        internal_code=error.code,
        message=error.message,
        data=ErrorDetail(field=error.field, reason=error.message),
    )
    return JSONResponse(
        status_code=error.status,
        headers={"X-Request-ID": request_id},
        content=payload.model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0] if error.errors() else {}
        location = first.get("loc", ())
        field = ".".join(str(part) for part in location) or None
        return error_response(
            request, AppError(422, "REQUEST_INVALID", "Invalid request", field=field)
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = {
            404: "ROUTE_NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(error.status_code, "HTTP_ERROR")
        return error_response(request, AppError(error.status_code, code, str(error.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=error)
        return error_response(request, AppError(500, "INTERNAL_ERROR", "Internal server error"))
