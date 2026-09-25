import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from risk_api.shared.api.response import error_response as serialize_error_response

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.field = field


def respond_app_error(request: Request, error: AppError) -> JSONResponse:
    return serialize_error_response(
        request,
        status=error.status,
        internal_code=error.code,
        message=error.message,
        field=error.field,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        if error.status >= 500:
            logger.error(
                "http.handled_error",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "internal_code": error.code,
                    "cause_type": type(error.__cause__).__name__ if error.__cause__ else None,
                },
            )
        return respond_app_error(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0] if error.errors() else {}
        location = first.get("loc", ())
        field = ".".join(str(part) for part in location) or None
        return respond_app_error(
            request, AppError(422, "REQUEST_INVALID", "Invalid request", field=field)
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = {
            404: "ROUTE_NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(error.status_code, "HTTP_ERROR")
        return respond_app_error(request, AppError(error.status_code, code, str(error.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "http.unhandled_error",
            exc_info=(type(error), error, error.__traceback__),
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return respond_app_error(request, AppError(500, "INTERNAL_ERROR", "Internal server error"))
