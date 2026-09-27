from dataclasses import dataclass


@dataclass(frozen=True)
class OverviewSampleSearchQuery:
    keyword: str
    category: str
    industry_code: str
    sort: str
    page: int
    page_size: int
