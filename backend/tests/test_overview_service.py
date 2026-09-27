import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from risk_api.modules.overview.errors import OverviewCompanyNotFound, OverviewUnavailable
from risk_api.modules.overview.query import OverviewSampleSearchQuery
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


def test_overview_service_searches_filters_sorts_and_pages_samples() -> None:
    async def scenario() -> None:
        payload = {
            "dataset": {"id": "sg"},
            "sampling": {"sampleCount": 3},
            "sampleCompanies": [
                {
                    "companyId": "A-1",
                    "name": "Alpha Trading",
                    "labelCategory": "healthy",
                    "status": "Live",
                    "ageYears": 4.0,
                    "industryCode": "46900",
                    "relationCount": 1,
                },
                {
                    "companyId": "B-2",
                    "name": "Beta Labs",
                    "labelCategory": "distress",
                    "status": "In Liquidation",
                    "ageYears": 8.0,
                    "industryCode": "62011",
                    "relationCount": 7,
                },
                {
                    "companyId": "C-3",
                    "name": "Gamma Trading",
                    "labelCategory": "unlabeled",
                    "status": "Struck Off",
                    "ageYears": None,
                    "industryCode": None,
                    "relationCount": 0,
                },
            ],
        }
        service = OverviewService(FakeRepository(payload))  # type: ignore[arg-type]

        dataset, sampling, samples, industry_codes, total = await service.search_samples(
            OverviewSampleSearchQuery(
                keyword="liquidation",
                category="distress",
                industry_code="all",
                sort="relations_desc",
                page=1,
                page_size=20,
            )
        )

        assert dataset == {"id": "sg"}
        assert sampling == {"sampleCount": 3}
        assert [sample["companyId"] for sample in samples] == ["B-2"]
        assert industry_codes == ["46900", "62011"]
        assert total == 1

        _, _, page, _, page_total = await service.search_samples(
            OverviewSampleSearchQuery(
                keyword="",
                category="all",
                industry_code="all",
                sort="age_desc",
                page=2,
                page_size=2,
            )
        )
        assert [sample["companyId"] for sample in page] == ["C-3"]
        assert page_total == 3

    asyncio.run(scenario())


def test_overview_service_returns_real_sample_profile_and_checks_identity() -> None:
    async def scenario() -> None:
        sample = {
            "companyId": "A-1",
            "name": "Alpha Trading",
            "labelCategory": "healthy",
            "status": "Live",
            "ageYears": 4.0,
            "industryCode": "46900",
            "relationCount": 1,
            "facts": {"country": "SG"},
            "relationProfile": {"totalCount": 1},
            "groups": [{"type": "industry", "value": "46900", "memberCount": 10}],
            "dataAvailability": {"registry": "available"},
        }
        payload = {
            "dataset": {"id": "sg-v2", "taskType": "entity_status_distress"},
            "sampling": {"sampleCount": 1},
            "sampleCompanies": [sample],
            "warnings": ["singapore_only_not_loan_default"],
        }
        service = OverviewService(FakeRepository(payload))  # type: ignore[arg-type]

        profile = await service.get_sample("sg-v2", "a-1")

        assert profile["profileVersion"] == 1
        assert profile["company"] == sample
        assert profile["observedLabel"] == {
            "category": "healthy",
            "status": "Live",
            "taskType": "entity_status_distress",
            "modelOutput": False,
        }
        assert profile["relations"] == {"totalCount": 1}
        assert profile["warnings"] == ["singapore_only_not_loan_default"]

        with pytest.raises(OverviewCompanyNotFound):
            await service.get_sample("another-dataset", "A-1")
        with pytest.raises(OverviewCompanyNotFound):
            await service.get_sample("sg-v2", "missing")

    asyncio.run(scenario())
