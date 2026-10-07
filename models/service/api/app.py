import hmac
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import DishkaRoute, FromDishka, setup_dishka
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from starlette.exceptions import HTTPException
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from service.api.schemas import (
    Envelope,
    ErrorEnvelope,
    RequestCapabilities,
    RequestEvents,
    RequestJob,
    RequestPredict,
    RequestSubmitJob,
    ResponseCapabilities,
    ResponseEvents,
    ResponseJob,
    ResponsePredict,
)
from service.config import Settings, configure_logging
from service.execution.store import Store
from service.runners.registry import capabilities
from service.runtime.service import Runtime

logger = logging.getLogger("riskgnn.http")


class Infrastructure(Provider):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    @provide(scope=Scope.APP)
    async def database(self) -> AsyncGenerator[AsyncEngine, None]:
        engine = create_async_engine(self.settings.database_url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def store(self, engine: AsyncEngine) -> Store:
        return Store(engine)

    @provide(scope=Scope.APP)
    async def storage(self) -> AsyncGenerator[AsyncClient, None]:
        async with AsyncClient(
            ClientConfig(
                bucket=self.settings.bucket,
                region="us-east-1",
                endpoint=self.settings.endpoint,
                use_path_style=True,
            )
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    def runtime(self, store: Store, storage: AsyncClient) -> Runtime:
        return Runtime(store, storage, self.settings)


router = APIRouter(
    route_class=DishkaRoute,
    responses={status: {"model": ErrorEnvelope} for status in (401, 404, 409, 422, 503)},
)


@router.post("/jobs/submit", response_model=Envelope[ResponseJob])
async def submit(body: RequestSubmitJob, request: Request, store: FromDishka[Store]):
    await store.submit(
        str(body.jobId),
        body.kind,
        body.payload.model_dump(mode="json", exclude_none=True),
        request.state.request_id,
    )
    return Envelope(data=await store.get(str(body.jobId)))


@router.post("/jobs/get", response_model=Envelope[ResponseJob])
async def get(body: RequestJob, store: FromDishka[Store]):
    return Envelope(data=await store.get(str(body.jobId)))


@router.post("/jobs/cancel", response_model=Envelope[ResponseJob])
async def cancel(body: RequestJob, store: FromDishka[Store]):
    await store.cancel(str(body.jobId))
    return Envelope(data=await store.get(str(body.jobId)))


@router.post("/jobs/events", response_model=Envelope[ResponseEvents])
async def events(body: RequestEvents, store: FromDishka[Store]):
    await store.get(str(body.jobId))
    return Envelope(data={"items": await store.events(str(body.jobId), body.after)})


@router.post("/artifacts/get", response_model=Envelope[ResponseJob])
async def artifact(body: RequestJob, store: FromDishka[Store]):
    return Envelope(data=await store.get(str(body.jobId)))


@router.post("/models/predict", response_model=Envelope[ResponsePredict])
async def predict(body: RequestPredict, runtime: FromDishka[Runtime]):
    return Envelope(data={"items": await runtime.predict(str(body.jobId), body.companyIds)})


@router.post("/models/capabilities", response_model=Envelope[ResponseCapabilities])
async def model_capabilities(body: RequestCapabilities):
    return Envelope(data={"items": capabilities()})


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings)
    container = make_async_container(Infrastructure(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await app.state.dishka_container.close()

    app = FastAPI(title="RiskGNN internal API", version="1.0.0", lifespan=lifespan)
    setup_dishka(container=container, app=app)

    def error(request: Request, status: int, code: str, message: str):
        return JSONResponse(
            {
                "code": status,
                "internal_code": code,
                "message": message,
                "data": {"field": None, "reason": message},
            },
            status_code=status,
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.middleware("http")
    async def policy(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        if request.url.path.startswith("/internal/") and not hmac.compare_digest(
            request.headers.get("Authorization", ""), f"Bearer {settings.token}"
        ):
            return error(request, 401, "SERVICE_UNAUTHORIZED", "Invalid service credential")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.log(
            logging.DEBUG if request.url.path == "/health/live" else logging.INFO,
            "http.completed",
            extra={
                "request_id": request.state.request_id,
                "path": request.url.path,
                "status": response.status_code,
            },
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(request, exc.status_code, "ROUTE_NOT_FOUND", "Route not found")

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        return error(request, 422, "REQUEST_INVALID", "Invalid request")

    @app.exception_handler(ValueError)
    async def conflict(request: Request, exc: ValueError):
        return error(request, 409, "MODEL_STATE_INVALID", str(exc))

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError):
        return error(request, 404, "MODEL_RESOURCE_NOT_FOUND", str(exc))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logger.exception("service.failed", extra={"request_id": request.state.request_id})
        return error(request, 503, "MODEL_SERVICE_UNAVAILABLE", "Model service unavailable")

    @app.get("/health/live", include_in_schema=False)
    async def live():
        return {"status": "ok"}

    app.include_router(router, prefix="/internal/v1")
    return app
