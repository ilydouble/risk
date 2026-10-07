from typing import Any

from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.errors import AppError
from risk_api.modules.modeling.workbench_model import Dataset, ModelVersion, Run


class ModelingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def owned(self, model: Any, owner: str, identity: str, *, lock: bool = False) -> Any:
        query = select(model).where(model.id == identity, model.owner_id == owner)
        if lock:
            query = query.with_for_update()
        item = await self.session.scalar(query)
        if item is None:
            raise AppError(404, "MODELING_RESOURCE_NOT_FOUND", "Resource not found")
        return item

    async def dataset(self, owner: str, identity: str, *, lock: bool = False) -> Dataset:
        return await self.owned(Dataset, owner, identity, lock=lock)

    async def run(self, owner: str, identity: str, *, lock: bool = False) -> Run:
        return await self.owned(Run, owner, identity, lock=lock)

    async def version(self, owner: str, identity: str) -> ModelVersion:
        return await self.owned(ModelVersion, owner, identity)

    async def page(self, model: Any, owner: str, page: int, size: int) -> tuple[list, int]:
        condition = model.owner_id == owner
        total = await self.session.scalar(select(func.count()).select_from(model).where(condition))
        rows: ScalarResult[Any] = await self.session.scalars(
            select(model)
            .where(condition)
            .order_by(model.created_at.desc(), model.id)
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows), int(total or 0)
