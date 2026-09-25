from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.page import Page, PageRequest

RiskLevel = Literal["low", "medium", "high"]


class CompanyDTO(BaseModel):
    id: str
    nameCn: str
    nameEn: str
    regNo: str
    country: str
    countryEn: str | None = None
    region: str
    regionEn: str | None = None
    sector: str
    sectorEn: str | None = None
    countryFlag: str
    industry: str
    industryEn: str | None = None
    creditScore: int
    riskLevel: RiskLevel
    defaultProb: float
    creditLimit: str
    updatedAt: str
    tags: list[str]
    tagsEn: list[str] | None = None


class CompanyFacts(BaseModel):
    established: str
    registeredCapital: str
    paidInCapital: str
    legalPerson: str
    actualController: str
    controllerStake: str
    employees: str
    listed: str
    ratingAgency: str
    mainBanks: str
    settlement: str
    revenue: str
    netMargin: str


class CompanyFactsEn(BaseModel):
    registeredCapital: str | None = None
    paidInCapital: str | None = None
    legalPerson: str | None = None
    actualController: str | None = None
    controllerStake: str | None = None
    employees: str | None = None
    listed: str | None = None
    ratingAgency: str | None = None
    mainBanks: str | None = None
    settlement: str | None = None
    revenue: str | None = None
    netMargin: str | None = None


class TimelineEvent(BaseModel):
    id: str
    date: str
    type: Literal["equity", "legal", "address", "finance", "risk", "award"]
    title: str
    titleEn: str | None = None
    desc: str
    descEn: str | None = None
    impact: Literal["positive", "neutral", "negative"]


class RiskFlag(BaseModel):
    id: str
    label: str
    labelEn: str | None = None
    level: RiskLevel
    category: str
    categoryEn: str | None = None
    desc: str
    descEn: str | None = None
    source: str
    detectedAt: str


class FiveCDimension(BaseModel):
    key: str
    label: str
    en: str
    weight: float
    score: float
    note: str
    noteEn: str | None = None


class RelatedParty(BaseModel):
    id: str
    name: str
    nameEn: str | None = None
    relation: str
    relationEn: str | None = None
    exposure: str
    exposureEn: str | None = None
    riskLevel: RiskLevel


class CompanyProfile(BaseModel):
    facts: CompanyFacts
    factsEn: CompanyFactsEn | None = None
    summary: str
    summaryEn: str | None = None
    timeline: list[TimelineEvent]
    riskFlags: list[RiskFlag]
    fiveC: list[FiveCDimension]
    relatedParties: list[RelatedParty]


class RequestSearchCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(default="", max_length=200)
    region: str = "all"
    sector: str = "all"
    risks: list[RiskLevel] = Field(default_factory=list)
    sort: Literal["score_desc", "score_asc", "dp_desc", "recent"] = "score_desc"
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseSearchCompany(Page[CompanyDTO]):
    pass


class RequestGetCompany(BaseModel):
    id: str


class ResponseGetCompany(BaseModel):
    company: CompanyDTO
    profile: CompanyProfile
    demo: Literal[True] = True
