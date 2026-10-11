import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from model_service.adapters.contracts import AdapterError
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


async def adapter_error(request: Request, exc: AdapterError):
    status = (
        422
        if exc.detail.code
        in {
            "ADAPTER_NOT_AVAILABLE",
            "ADAPTER_OPERATION_UNSUPPORTED",
            "ADAPTER_PARAMETERS_INVALID",
            "ADAPTER_INPUT_INVALID",
            "ADAPTER_INPUT_INCOMPATIBLE",
            "RISKGNN_INPUT_INVALID",
        }
        else 503
    )
    return error_response(
        request, status, exc.detail.code, exc.detail.message, field=exc.detail.path
    )


def register_error_handlers(app: FastAPI) -> None:
    app.exception_handler(AdapterError)(adapter_error)
    app.exception_handler(HTTPException)(http_error)
    app.exception_handler(RequestValidationError)(invalid)
    app.exception_handler(ValueError)(conflict)
    app.exception_handler(KeyError)(missing)
    app.exception_handler(Exception)(unexpected)
