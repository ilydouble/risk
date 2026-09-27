from typing import Any

from risk_api.modules.overview.errors import OverviewUnavailable
from risk_api.modules.overview.repository import OverviewRepository


class OverviewService:
    def __init__(self, repository: OverviewRepository):
        self.repository = repository

    async def get(self) -> dict[str, Any]:
        snapshot = await self.repository.latest()
        if snapshot is None:
            raise OverviewUnavailable()
        return snapshot.payload
