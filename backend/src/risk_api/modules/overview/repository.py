from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.overview.model import OverviewSnapshot


class OverviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def latest(self) -> OverviewSnapshot | None:
        return await self.session.scalar(
            select(OverviewSnapshot)
            .order_by(OverviewSnapshot.created_at.desc(), OverviewSnapshot.id.desc())
            .limit(1)
        )
