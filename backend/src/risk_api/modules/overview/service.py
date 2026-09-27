from typing import Any

from risk_api.modules.overview.errors import OverviewCompanyNotFound, OverviewUnavailable
from risk_api.modules.overview.query import OverviewSampleSearchQuery
from risk_api.modules.overview.repository import OverviewRepository


class OverviewService:
    def __init__(self, repository: OverviewRepository):
        self.repository = repository

    async def get(self) -> dict[str, Any]:
        snapshot = await self.repository.latest()
        if snapshot is None:
            raise OverviewUnavailable()
        return snapshot.payload

    async def search_samples(
        self, query: OverviewSampleSearchQuery
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str], int]:
        payload = await self.get()
        all_samples: list[dict[str, Any]] = payload["sampleCompanies"]
        industry_codes = sorted(
            {
                str(item["industryCode"])
                for item in all_samples
                if item.get("industryCode")
            }
        )
        keyword = query.keyword.strip().casefold()
        samples = [
            item
            for item in all_samples
            if (
                not keyword
                or keyword
                in " ".join(
                    (
                        str(item.get("companyId", "")),
                        str(item.get("name", "")),
                        str(item.get("status", "")),
                    )
                ).casefold()
            )
            and (query.category == "all" or item["labelCategory"] == query.category)
            and (
                query.industry_code == "all"
                or item.get("industryCode") == query.industry_code
            )
        ]
        if query.sort == "age_desc":
            samples.sort(
                key=lambda item: (
                    item.get("ageYears") is None,
                    -float(item.get("ageYears") or 0),
                    str(item["name"]).casefold(),
                )
            )
        elif query.sort == "relations_desc":
            samples.sort(
                key=lambda item: (
                    -int(item["relationCount"]),
                    str(item["name"]).casefold(),
                )
            )
        else:
            samples.sort(
                key=lambda item: (
                    str(item["name"]).casefold(),
                    str(item["companyId"]),
                )
            )
        total = len(samples)
        start = (query.page - 1) * query.page_size
        return (
            payload["dataset"],
            payload["sampling"],
            samples[start : start + query.page_size],
            industry_codes,
            total,
        )

    async def get_sample(self, dataset_id: str, company_id: str) -> dict[str, Any]:
        payload = await self.get()
        if payload["dataset"]["id"] != dataset_id:
            raise OverviewCompanyNotFound()
        normalized_id = company_id.strip().casefold()
        sample = next(
            (
                item
                for item in payload["sampleCompanies"]
                if str(item["companyId"]).casefold() == normalized_id
            ),
            None,
        )
        if sample is None:
            raise OverviewCompanyNotFound()
        return {
            "profileVersion": 1,
            "dataset": payload["dataset"],
            "sampling": payload["sampling"],
            "company": sample,
            "facts": sample["facts"],
            "observedLabel": {
                "category": sample["labelCategory"],
                "status": sample["status"],
                "taskType": payload["dataset"]["taskType"],
                "modelOutput": False,
            },
            "relations": sample["relationProfile"],
            "groups": sample["groups"],
            "dataAvailability": sample["dataAvailability"],
            "warnings": payload["warnings"],
        }
