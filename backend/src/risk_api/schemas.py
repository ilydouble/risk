from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")
Status = TypeVar("Status", bound=int)
InternalCode = TypeVar("InternalCode", bound=str)
RiskLevel = Literal["low", "medium", "high"]


class ApiEnvelope(BaseModel, Generic[T]):  # noqa: UP046  Pydantic generic schema naming.
    code: int
    internal_code: str
    message: str
    data: T | None


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str


class ErrorEnvelope(BaseModel, Generic[Status, InternalCode]):  # noqa: UP046
    code: Status
    internal_code: InternalCode
    message: str
    data: ErrorDetail


COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorEnvelope[Literal[403], Literal["REQUEST_ORIGIN_INVALID"]]},
    422: {"model": ErrorEnvelope[Literal[422], Literal["REQUEST_INVALID"]]},
    500: {"model": ErrorEnvelope[Literal[500], Literal["INTERNAL_ERROR"]]},
}


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
    keyword: str = Field(default="", max_length=200)
    region: str = "all"
    sector: str = "all"
    risks: list[RiskLevel] = Field(default_factory=list)
    sort: Literal["score_desc", "score_asc", "dp_desc", "recent"] = "score_desc"
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=100)


class ResponseSearchCompany(BaseModel):
    items: list[CompanyDTO]
    total: int
    page: int
    pageSize: int


class RequestGetCompany(BaseModel):
    id: str


class ResponseGetCompany(BaseModel):
    company: CompanyDTO
    profile: CompanyProfile
    demo: Literal[True] = True


class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal[
        "company",
        "owner",
        "subsidiary",
        "supplier",
        "guarantor",
        "client",
        "counterparty",
        "person",
        "bank",
        "fund",
    ]
    riskLevel: RiskLevel
    hop: int
    relation: str
    exposure: str
    industry: str | None = None
    country: str | None = None
    companyId: str | None = None
    note: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal["equity", "control", "guarantee", "supply", "trade", "loan"]
    label: str
    riskFlow: bool
    strength: float


class GraphData(BaseModel):
    rootId: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RequestGetGraph(BaseModel):
    companyId: str
    lang: Literal["zh", "en"] = "zh"
    depth: int = Field(default=3, ge=2, le=3)


class ResponseGetGraph(BaseModel):
    graph: GraphData
    demo: Literal[True] = True


class ShapFeature(BaseModel):
    id: str
    label: str
    category: str
    value: str
    contribution: float
    desc: str


class CommunityBenchmark(BaseModel):
    key: str
    label: str
    tag: str
    sampleSize: int
    avgScore: float
    avgDefaultProb: float
    percentile: float
    goodRate: float
    diff: float


class ScoreDetail(BaseModel):
    baseValue: int
    finalScore: int
    grade: str
    gradeNote: str
    riskPercentile: float
    defaultProb: float
    pdBase: float
    pdDelta: float
    confidence: float
    modelVersion: str
    evaluatedAt: str
    positiveCount: int
    negativeCount: int
    features: list[ShapFeature]
    benchmarks: list[CommunityBenchmark]


class RequestGetScore(BaseModel):
    companyId: str
    lang: Literal["zh", "en"] = "zh"


class ResponseGetScore(BaseModel):
    company: CompanyDTO
    detail: ScoreDetail
    demo: Literal[True] = True


class RequestLogin(BaseModel):
    username: str
    password: str


class ResponseLogin(BaseModel):
    userId: str
    username: str
    displayName: str
    expiresIn: int


class RequestLogout(BaseModel):
    pass


class ResponseLogout(BaseModel):
    loggedOut: bool


class RequestMe(BaseModel):
    pass


class ResponseMe(BaseModel):
    userId: str
    username: str
    displayName: str


class DocumentDTO(BaseModel):
    id: str
    companyId: str
    filename: str
    contentType: str
    size: int
    createdAt: str


class RequestCreateUpload(BaseModel):
    companyId: str
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    size: int = Field(gt=0, le=10_000_000)


class ResponseCreateUpload(BaseModel):
    documentId: str
    url: str
    headers: dict[str, str]
    expiresIn: int = 60


class RequestCompleteUpload(BaseModel):
    documentId: str


class ResponseCompleteUpload(BaseModel):
    document: DocumentDTO


class RequestListDocuments(BaseModel):
    companyId: str


class ResponseListDocuments(BaseModel):
    items: list[DocumentDTO]


class RequestCreateDownload(BaseModel):
    documentId: str


class ResponseCreateDownload(BaseModel):
    url: str
    expiresIn: int = 60
