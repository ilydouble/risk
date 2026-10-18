from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from model_service.dependencies import Infrastructure
from model_service.modules.artifacts.api.route import router as artifacts_router
from model_service.modules.decision.api.route import router as decision_router
from model_service.modules.decision.service import DecisionService
from model_service.modules.jobs.api.route import router as jobs_router
from model_service.modules.models.api.route import router as models_router
from model_service.shared.api.errors import register_error_handlers
from model_service.shared.api.middleware import create_request_policy
from model_service.shared.config import Settings
from model_service.shared.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        service = await app.state.dishka_container.get(DecisionService)
        await service.start()
        yield
    finally:
        await app.state.dishka_container.close()


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings)
    container = make_async_container(Infrastructure(settings))
    app = FastAPI(title="RiskGNN internal API", version="1.0.0", lifespan=lifespan)
    setup_dishka(container=container, app=app)
    register_error_handlers(app)
    app.middleware("http")(create_request_policy(settings))

    @app.get("/health/live", include_in_schema=False)
    async def live():
        return {"status": "ok"}

    app.include_router(jobs_router, prefix="/internal/v1/jobs")
    app.include_router(artifacts_router, prefix="/internal/v1/artifacts")
    app.include_router(models_router, prefix="/internal/v1/models")
    app.include_router(decision_router, prefix="/internal/v1/decision")
    return app
