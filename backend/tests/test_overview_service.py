import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from risk_api.modules.overview.errors import OverviewUnavailable
from risk_api.modules.overview.service import OverviewService


class FakeRepository:
    def __init__(self, payload: dict[str, Any] | None):
        self.payload = payload

    async def latest(self) -> Any:
        return None if self.payload is None else SimpleNamespace(payload=self.payload)


def test_overview_service_returns_latest_snapshot() -> None:
    async def scenario() -> None:
        payload = {"snapshotVersion": 1}
        service = OverviewService(FakeRepository(payload))  # type: ignore[arg-type]
        assert await service.get() == payload

    asyncio.run(scenario())


def test_overview_service_reports_missing_import() -> None:
    async def scenario() -> None:
        service = OverviewService(FakeRepository(None))  # type: ignore[arg-type]
        with pytest.raises(OverviewUnavailable) as error:
            await service.get()
        assert error.value.code == "OVERVIEW_DATA_UNAVAILABLE"

    asyncio.run(scenario())
