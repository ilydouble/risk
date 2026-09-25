"""HTTP request policy and bounded completion logs."""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from risk_api.errors import AppError, respond_app_error
from risk_api.shared.config import settings
from risk_api.shared.logging import request_log_context

logger = logging.getLogger("risk_api.http")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is None:
        return "<unmatched>"
    fastapi_scope = request.scope.get("fastapi")
    if isinstance(fastapi_scope, dict):
        # FastAPI's nested includes keep the full prefix here; route.path is local to its router.
        context = fastapi_scope.get("effective_route_context")
        full_path = getattr(context, "path", None)
        if isinstance(full_path, str):
            return full_path
    return getattr(route, "path", "<unmatched>")


async def request_policy(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = perf_counter()
    status = 500
    internal_code = "INTERNAL_ERROR"
    response: Response
    with request_log_context(request.state.request_id):
        try:
            if request.method == "POST" and request.url.path.startswith("/api/"):
                origin = request.headers.get("origin")
                if origin not in settings.allowed_origin.split(","):
                    origin_error = AppError(403, "REQUEST_ORIGIN_INVALID", "Origin is not allowed")
                    response = respond_app_error(request, origin_error)
                else:
                    response = await call_next(request)
            else:
                response = await call_next(request)
            status = response.status_code
            internal_code = getattr(
                request.state,
                "internal_code",
                "SUCCESS" if status < 400 else "HTTP_ERROR",
            )
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        finally:
            # Uvicorn access logs are disabled; keep one request summary here.
            if request.url.path != "/health/live" or status != 200:
                level = logging.INFO
                if status >= 500:
                    level = logging.ERROR
                elif status >= 400:
                    level = logging.WARNING
                logger.log(
                    level,
                    "http.request_completed",
                    extra={
                        "method": request.method,
                        "route": _route_template(request),
                        "status": status,
                        "internal_code": internal_code,
                        "duration_ms": round((perf_counter() - started) * 1000, 2),
                    },
                )
