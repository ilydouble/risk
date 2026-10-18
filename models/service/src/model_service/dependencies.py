from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from model_service.modules.decision.service import DecisionService
from model_service.modules.decision.settings import DecisionSettings
from model_service.modules.jobs.repository import Store
from model_service.modules.models.service import Runtime
from model_service.shared.config import Settings
from model_service.shared.db import create_engine


class Infrastructure(Provider):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    @provide(scope=Scope.APP)
    async def decision(self) -> AsyncGenerator[DecisionService, None]:
        service = DecisionService(DecisionSettings())
        try:
            yield service
        finally:
            await service.close()

    @provide(scope=Scope.APP)
    async def database(self) -> AsyncGenerator[AsyncEngine, None]:
        engine = create_engine(self.settings)
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
