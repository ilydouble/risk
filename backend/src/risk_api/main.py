import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from risk_api.dependencies import InfrastructureProvider
from risk_api.errors import AppError, register_error_handlers, respond_app_error
from risk_api.modules.auth.api.route import router as auth_router
from risk_api.modules.company.api.route import router as company_router
from risk_api.modules.document.api.route import router as document_router
from risk_api.modules.graph.api.route import router as graph_router
from risk_api.modules.score.api.route import router as score_router
from risk_api.shared.config import settings
from risk_api.shared.logging import configure_logging, request_log_context

logger = logging.getLogger("risk_api.http")

container = make_async_container(InfrastructureProvider(), FastapiProvider())


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is None:
        return "<unmatched>"
    # Static routes can use the full path; dynamic routes keep placeholders out of logs.
    return getattr(route, "path", "<unmatched>") if request.path_params else request.url.path


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    configure_logging(settings.log_level, output_format=settings.log_format)
    logger.info("backend.started")
    try:
        yield
    finally:
        await container.close()
        logger.info("backend.stopped")


app = FastAPI(title="Risk Workbench API", version="0.1.0", lifespan=lifespan)
setup_dishka(container, app)
register_error_handlers(app)


@app.middleware("http")
async def request_policy(request: Request, call_next):  # type: ignore[no-untyped-def]
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = perf_counter()
    status = 500
    internal_code = "INTERNAL_ERROR"
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
            # The middleware logs one bounded summary per request; Uvicorn access logs are disabled.
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


@app.get("/health/live", include_in_schema=False)
async def live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(company_router, prefix="/api/v1/company", tags=["company"])
app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(score_router, prefix="/api/v1/score", tags=["score"])
app.include_router(document_router, prefix="/api/v1/document", tags=["document"])
