from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.page import Page, PageRequest

OverviewWarning = Literal[
    "singapore_only_not_loan_default",
    "administrative_terminations_unlabeled",
    "age_time_confound",
    "weak_address_graph",
    "capital_litigation_unavailable",
]
OverviewLabelCategory = Literal["healthy", "distress", "unlabeled"]
OverviewAvailability = Literal[
    "available",
    "no_records",
    "source_unavailable",
    "not_in_dataset",
    "not_run",
]


class RequestGetOverview(BaseModel):
    pass


class OverviewDatasetDTO(BaseModel):
    id: str
    name: str
    country: Literal["SG"]
    taskType: Literal["entity_status_distress"]
    generatedAt: str
    sourceScope: str
    sourceArchiveSha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class OverviewStatsDTO(BaseModel):
    companyCount: int = Field(ge=0)
    labeledCount: int = Field(ge=0)
    distressCount: int = Field(ge=0)
    healthyCount: int = Field(ge=0)
    unlabeledCount: int = Field(ge=0)
    edgeCount: int = Field(ge=0)


class DistributionItemDTO(BaseModel):
    key: Literal["healthy", "distress", "unlabeled"]
    value: int = Field(ge=0)


class AgeDistributionItemDTO(BaseModel):
    bucket: Literal["0_3", "4_10", "11_20", "21_50", "50_plus"]
    total: int = Field(ge=0)
    labeled: int = Field(ge=0)
    distress: int = Field(ge=0)


class StatusDistributionItemDTO(BaseModel):
    status: str
    count: int = Field(ge=0)


class EdgeTypeItemDTO(BaseModel):
    type: str
    count: int = Field(ge=0)


class GraphComponentDTO(BaseModel):
    key: Literal["relations", "industry", "area", "qualify"]
    rowCount: int = Field(ge=0)
    groupCount: int = Field(ge=0)


class OverviewSamplingDTO(BaseModel):
    strategy: Literal["deterministic_stratified_hash"]
    requestedPerClass: int = Field(ge=1)
    sampleCount: int = Field(ge=0)
    representative: Literal[False]


class OverviewSampleCompanyDTO(BaseModel):
    companyId: str
    name: str
    labelCategory: OverviewLabelCategory
    status: str
    ageYears: float | None
    industryCode: str | None
    relationCount: int = Field(ge=0)


class OverviewCompanyFactsDTO(BaseModel):
    country: str | None
    setupTimeMonths: float | None = Field(ge=0)
    industryDivisionCode: str | None
    officerCount: int | None = Field(ge=0)
    nameChangeCount: int | None = Field(ge=0)
    hasUnit: bool | None
    registeredCapital: float | None = Field(ge=0)
    paidCapital: float | None = Field(ge=0)


class OverviewRelationCountDTO(BaseModel):
    type: str
    count: int = Field(ge=0)


class OverviewRelatedCompanyDTO(BaseModel):
    companyId: str
    name: str
    status: str
    labelCategory: OverviewLabelCategory
    relationType: str
    weight: float = Field(gt=0)


class OverviewRelationProfileDTO(BaseModel):
    totalCount: int = Field(ge=0)
    byType: list[OverviewRelationCountDTO]
    neighbors: list[OverviewRelatedCompanyDTO]
    displayedCount: int = Field(ge=0)
    truncated: bool


class OverviewGroupMembershipDTO(BaseModel):
    type: Literal["industry", "area", "qualify"]
    value: str
    memberCount: int = Field(ge=1)


class OverviewDataAvailabilityDTO(BaseModel):
    registry: OverviewAvailability
    relations: OverviewAvailability
    capital: OverviewAvailability
    litigation: OverviewAvailability
    bankCredit: OverviewAvailability
    modelRisk: OverviewAvailability


class OverviewObservedLabelDTO(BaseModel):
    category: OverviewLabelCategory
    status: str
    taskType: Literal["entity_status_distress"]
    modelOutput: Literal[False] = False


class OverviewQualityDTO(BaseModel):
    labeledRate: float = Field(ge=0, le=1)
    distressRateWithinLabeled: float = Field(ge=0, le=1)
    ordinaryEdgeCoverageWithinLabeled: float = Field(ge=0, le=1)
    capitalCoverage: float = Field(ge=0, le=1)
    litigationRows: int = Field(ge=0)


class ResponseGetOverview(BaseModel):
    snapshotVersion: Literal[1]
    dataset: OverviewDatasetDTO
    stats: OverviewStatsDTO
    labelDistribution: list[DistributionItemDTO]
    ageDistribution: list[AgeDistributionItemDTO]
    statusDistribution: list[StatusDistributionItemDTO]
    edgeTypes: list[EdgeTypeItemDTO]
    graphComponents: list[GraphComponentDTO]
    sampling: OverviewSamplingDTO
    sampleCompanies: list[OverviewSampleCompanyDTO]
    quality: OverviewQualityDTO
    warnings: list[OverviewWarning]


class RequestSearchOverviewCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(default="", max_length=200)
    category: Literal["all", "healthy", "distress", "unlabeled"] = "all"
    industryCode: str = Field(default="all", max_length=32)
    sort: Literal["name_asc", "age_desc", "relations_desc"] = "name_asc"
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseSearchOverviewCompany(Page[OverviewSampleCompanyDTO]):
    dataset: OverviewDatasetDTO
    sampling: OverviewSamplingDTO
    industryCodes: list[str]


class RequestGetOverviewCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datasetId: str = Field(min_length=1, max_length=120)
    companyId: str = Field(min_length=1, max_length=120)


class ResponseGetOverviewCompany(BaseModel):
    profileVersion: Literal[1]
    dataset: OverviewDatasetDTO
    sampling: OverviewSamplingDTO
    company: OverviewSampleCompanyDTO
    facts: OverviewCompanyFactsDTO
    observedLabel: OverviewObservedLabelDTO
    relations: OverviewRelationProfileDTO
    groups: list[OverviewGroupMembershipDTO]
    dataAvailability: OverviewDataAvailabilityDTO
    warnings: list[OverviewWarning]
