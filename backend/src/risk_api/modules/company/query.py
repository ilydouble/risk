from dataclasses import dataclass


@dataclass(frozen=True)
class CompanySearchQuery:
    keyword: str
    region: str
    sector: str
    risks: tuple[str, ...]
    sort: str
    page: int
    page_size: int
