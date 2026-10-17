import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from model_service.execution.contracts import ExecutionError
from model_service.shared.api.response import error_response

logger = logging.getLogger("riskgnn.http")


async def http_error(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "ROUTE_NOT_FOUND", "Route not found")


async def invalid(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "REQUEST_INVALID", "Invalid request")


async def conflict(request: Request, exc: ValueError):
    return error_response(request, 409, "MODEL_STATE_INVALID", str(exc))


async def missing(request: Request, exc: KeyError):
    return error_response(request, 404, "MODEL_RESOURCE_NOT_FOUND", str(exc))


async def unexpected(request: Request, exc: Exception):
    logger.exception("service.failed", extra={"request_id": request.state.request_id})
    return error_response(request, 503, "MODEL_SERVICE_UNAVAILABLE", "Model service unavailable")


async def execution_error(request: Request, exc: ExecutionError):
    status = (
        409
        if exc.detail.code in {"MODELING_CONFIG_STALE", "MODEL_EXPLANATION_UNAVAILABLE"}
        else (
            422
            if exc.detail.code
            in {
                "MODEL_RUNTIME_INCOMPATIBLE",
                "EXECUTION_OPERATION_UNSUPPORTED",
                "EXECUTION_PARAMETERS_INVALID",
                "EXECUTION_INPUT_INVALID",
                "EXECUTION_INPUT_INCOMPATIBLE",
                "MODEL_INPUT_INVALID",
            }
            else 503
        )
    )
    return error_response(
        request, status, exc.detail.code, exc.detail.message, field=exc.detail.path
    )


def register_error_handlers(app: FastAPI) -> None:
    app.exception_handler(ExecutionError)(execution_error)
    app.exception_handler(HTTPException)(http_error)
    app.exception_handler(RequestValidationError)(invalid)
    app.exception_handler(ValueError)(conflict)
    app.exception_handler(KeyError)(missing)
    app.exception_handler(Exception)(unexpected)
