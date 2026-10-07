import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from risk_api.dependencies import InfrastructureProvider
from risk_api.errors import register_error_handlers
from risk_api.modules.auth.api.route import router as auth_router
from risk_api.modules.company.api.route import router as company_router
from risk_api.modules.document.api.route import router as document_router
from risk_api.modules.graph.api.route import router as graph_router
from risk_api.modules.modeling.api.route import router as modeling_router
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.dispatch import dispatch_loop
from risk_api.modules.overview.api.route import router as overview_router
from risk_api.modules.score.api.route import router as score_router
from risk_api.shared.api.middleware import request_policy
from risk_api.shared.config import settings
from risk_api.shared.db import session_factory
from risk_api.shared.logging import configure_logging

logger = logging.getLogger("risk_api.http")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    dispatcher = None
    try:
        configure_logging(settings.log_level, output_format=settings.log_format)
        client = await app.state.dishka_container.get(ModelClient)
        dispatcher = asyncio.create_task(dispatch_loop(session_factory, client))
        logger.info("backend.started")
        yield
    finally:
        if dispatcher:
            dispatcher.cancel()
            await asyncio.gather(dispatcher, return_exceptions=True)
        await app.state.dishka_container.close()
        logger.info("backend.stopped")


def create_app() -> FastAPI:
    container = make_async_container(InfrastructureProvider(), FastapiProvider())
    app = FastAPI(title="Risk Workbench API", version="0.1.0", lifespan=lifespan)
    setup_dishka(container=container, app=app)
    register_error_handlers(app)
    app.middleware("http")(request_policy)

    @app.get("/health/live", include_in_schema=False)
    async def live() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(company_router, prefix="/api/v1/company", tags=["company"])
    app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
    app.include_router(score_router, prefix="/api/v1/score", tags=["score"])
    app.include_router(document_router, prefix="/api/v1/document", tags=["document"])
    app.include_router(modeling_router, prefix="/api/v1/modeling", tags=["modeling"])
    app.include_router(overview_router, prefix="/api/v1/overview", tags=["overview"])
    return app
