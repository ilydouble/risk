import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from stellarmesh_logging import JSONFormatter

from risk_api.config import settings
from risk_api.dependencies import InfrastructureProvider
from risk_api.errors import AppError, register_error_handlers
from risk_api.modules.auth.api import router as auth_router
from risk_api.modules.company.api import router as company_router
from risk_api.modules.document.api import router as document_router
from risk_api.modules.graph.api import router as graph_router
from risk_api.modules.score.api import router as score_router

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

container = make_async_container(InfrastructureProvider(), FastapiProvider())


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    yield
    await container.close()


app = FastAPI(title="Risk Workbench API", version="0.1.0", lifespan=lifespan)
setup_dishka(container, app)
register_error_handlers(app)


@app.middleware("http")
async def request_policy(request: Request, call_next):  # type: ignore[no-untyped-def]
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
    if request.method == "POST" and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin not in settings.allowed_origin.split(","):
            raise_error = AppError(403, "REQUEST_ORIGIN_INVALID", "Origin is not allowed")
            from risk_api.errors import error_response

            return error_response(request, raise_error)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.get("/health/live", include_in_schema=False)
async def live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(company_router, prefix="/api/v1/company", tags=["company"])
app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(score_router, prefix="/api/v1/score", tags=["score"])
app.include_router(document_router, prefix="/api/v1/document", tags=["document"])
