import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.errors import AppError
from risk_api.modules.data_qa.query import CompiledQuery
from risk_api.modules.modeling.workbench_model import Dataset, ModelVersion, Run


class DataQARepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @asynccontextmanager
    async def readonly(self):
        async with asyncio.timeout(5), self.session.begin():
            await self.session.execute(text("SET TRANSACTION READ ONLY"))
            await self.session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
            yield

    async def catalog(self, owner: str) -> dict:
        async with self.readonly():
            datasets = await self.session.execute(
                select(Dataset.id, Dataset.name)
                .where(Dataset.owner_id == owner)
                .order_by(Dataset.created_at.desc())
                .limit(201)
            )
            models = await self.session.execute(
                select(ModelVersion.id, ModelVersion.name, Run.dataset_id)
                .join(Run, Run.id == ModelVersion.run_id)
                .join(Dataset, Dataset.id == Run.dataset_id)
                .where(
                    ModelVersion.owner_id == owner, Run.owner_id == owner, Dataset.owner_id == owner
                )
                .order_by(ModelVersion.created_at.desc())
                .limit(201)
            )
            data, versions = list(datasets.mappings()), list(models.mappings())
            return {
                "datasets": [dict(row) for row in data[:200]],
                "models": [
                    {"id": row["id"], "name": row["name"], "datasetId": row["dataset_id"]}
                    for row in versions[:200]
                ],
                "truncated": len(data) > 200 or len(versions) > 200,
            }

    async def check_scope(self, owner: str, dataset: str | None, model: str | None):
        async with self.readonly():
            if dataset and not await self.session.scalar(
                select(Dataset.id).where(Dataset.owner_id == owner, Dataset.id == dataset)
            ):
                raise AppError(404, "DATA_QA_SCOPE_NOT_FOUND", "数据集不存在或无权访问")
            if model:
                statement = (
                    select(ModelVersion.id)
                    .join(Run, Run.id == ModelVersion.run_id)
                    .join(Dataset, Dataset.id == Run.dataset_id)
                    .where(
                        ModelVersion.id == model,
                        ModelVersion.owner_id == owner,
                        Run.owner_id == owner,
                        Dataset.owner_id == owner,
                    )
                )
                if dataset:
                    statement = statement.where(Dataset.id == dataset)
                if not await self.session.scalar(statement):
                    raise AppError(404, "DATA_QA_SCOPE_NOT_FOUND", "模型不存在或不属于所选数据集")

    async def execute(self, query: CompiledQuery) -> list[dict]:
        async with self.readonly():
            return [dict(row) for row in (await self.session.execute(query.statement)).mappings()]
