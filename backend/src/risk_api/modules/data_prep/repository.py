from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from risk_api.errors import AppError
from risk_api.modules.data_prep.model import Preparation


class PreparationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, owner: str, identity: str, *, lock: bool = False) -> Preparation:
        query = select(Preparation).where(Preparation.owner_id == owner, Preparation.id == identity)
        if lock:
            query = query.with_for_update()
        item = await self.session.scalar(query)
        if item is None:
            raise AppError(404, "DATA_PREP_NOT_FOUND", "数据准备记录不存在或无权访问")
        return item

    async def list(self, owner: str, *, workbench_only: bool = False) -> list[Preparation]:
        query = select(Preparation).options(defer(Preparation.source)).where(
            Preparation.owner_id == owner
        )
        if workbench_only:
            query = query.where(Preparation.in_workbench.is_(True))
        return list(await self.session.scalars(
            query.order_by(Preparation.updated_at.desc(), Preparation.id).limit(101)
        ))

    async def save(self, item: Preparation) -> Preparation:
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def by_sha(self, owner: str, sha: str) -> Preparation | None:
        return await self.session.scalar(select(Preparation).where(
            Preparation.owner_id == owner, Preparation.source_sha == sha,
        ))
