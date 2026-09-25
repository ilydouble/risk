from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from neo4j import AsyncDriver, AsyncGraphDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from risk_api.modules.auth.repository import UserRepository
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.repository import CompanyRepository
from risk_api.modules.company.service import CompanyService
from risk_api.modules.document.repository import DocumentRepository
from risk_api.modules.document.service import DocumentService
from risk_api.modules.graph.repository import GraphRepository
from risk_api.modules.graph.service import GraphService
from risk_api.modules.score.service import ScoreService
from risk_api.shared.config import settings
from risk_api.shared.db import session_factory


class InfrastructureProvider(Provider):
    @provide(scope=Scope.APP)
    async def redis(self) -> AsyncIterator[Redis]:
        client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    @provide(scope=Scope.APP)
    async def graph(self) -> AsyncIterator[AsyncDriver]:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        try:
            yield driver
        finally:
            await driver.close()

    @provide(scope=Scope.APP)
    async def storage(self) -> AsyncIterator[AsyncClient]:
        config = ClientConfig(
            bucket=settings.storage_bucket,
            region=settings.storage_region,
            endpoint=settings.storage_endpoint,
            presign_endpoint=settings.storage_public_endpoint,
            use_path_style=True,
            default_presign_ttl=60,
        )
        async with AsyncClient(config) as client:
            yield client

    @provide(scope=Scope.REQUEST)
    async def database(self) -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def user_repository(self, session: AsyncSession) -> UserRepository:
        return UserRepository(session)

    @provide(scope=Scope.REQUEST)
    def auth_service(self, users: UserRepository, redis: Redis) -> AuthService:
        return AuthService(users, redis)

    @provide(scope=Scope.REQUEST)
    def company_repository(self, session: AsyncSession) -> CompanyRepository:
        return CompanyRepository(session)

    @provide(scope=Scope.REQUEST)
    def company_service(self, repository: CompanyRepository) -> CompanyService:
        return CompanyService(repository)

    @provide(scope=Scope.REQUEST)
    def score_service(self, companies: CompanyService) -> ScoreService:
        return ScoreService(companies)

    @provide(scope=Scope.REQUEST)
    def graph_repository(self, driver: AsyncDriver) -> GraphRepository:
        return GraphRepository(driver)

    @provide(scope=Scope.REQUEST)
    def graph_service(self, companies: CompanyService, repository: GraphRepository) -> GraphService:
        return GraphService(companies, repository)

    @provide(scope=Scope.REQUEST)
    def document_repository(self, session: AsyncSession) -> DocumentRepository:
        return DocumentRepository(session)

    @provide(scope=Scope.REQUEST)
    def document_service(
        self, companies: CompanyService, repository: DocumentRepository, storage: AsyncClient
    ) -> DocumentService:
        return DocumentService(companies, repository, storage)
