from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from risk_api.modules.data_prep.conversion import ConversionPlan
from risk_api.shared.api.model_connection import ModelConnection


class RequestInspectData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    contentBase64: str = Field(min_length=1, max_length=3_000_000)


class RequestCaseFile(RequestInspectData):
    contentBase64: str = Field(min_length=1, max_length=90_000_000)


class RequestInspectCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[RequestCaseFile] = Field(min_length=1, max_length=8)
    preparationId: UUID | None = None


class CaseFileProfile(BaseModel):
    filename: str
    sha256: str
    size: int
    role: Literal["enterprises", "graph"]
    nodeCount: int = 0
    edgeCount: int = 0
    hyperedgeCount: int = 0
    relationTypes: dict[str, int] = Field(default_factory=dict)
    groupTypes: dict[str, int] = Field(default_factory=dict)


class ValueFrequency(BaseModel):
    value: str
    count: int


class NumericSummary(BaseModel):
    min: str
    median: str
    max: str
    mean: str
    q1: str
    q3: str
    outlierCount: int


class QualityIssue(BaseModel):
    code: str
    message: str
    count: int
    field: str | None = None


class KeyCandidate(BaseModel):
    field: str
    kind: Literal["entity_key", "relation_key"]
    nonMissingCount: int
    duplicateValues: int


class LabelCandidate(BaseModel):
    field: str
    values: list[ValueFrequency]
    missingCount: int
    distinctCount: int
    minorityShare: float | None = None


class FieldProfile(BaseModel):
    name: str
    missingCount: int
    distinctCount: int
    numericRate: float
    dateRate: float = 0
    typeHint: Literal["empty", "identifier", "number", "date", "mixed", "category", "text"] = "text"
    whitespaceCount: int = 0
    leadingZeroCount: int = 0
    topValues: list[ValueFrequency] = Field(default_factory=list)
    numericSummary: NumericSummary | None = None
    examples: list[str]


class ResponseInspectData(BaseModel):
    preparationId: str | None = None
    caseFiles: list[CaseFileProfile] = Field(default_factory=list)
    primaryFilename: str | None = None
    previousPreparationId: str | None = None
    sha256: str
    rowCount: int
    rowsWithMissing: int = 0
    duplicateRows: int
    fields: list[FieldProfile]
    issues: list[QualityIssue] = Field(default_factory=list)
    keyCandidates: list[KeyCandidate] = Field(default_factory=list)
    labelCandidates: list[LabelCandidate] = Field(default_factory=list)
    sampleRows: list[dict[str, str]]


class RequestSuggestMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: ResponseInspectData
    connection: ModelConnection | None = None
    maxTokens: int = Field(default=4096, ge=256, le=16384)


class RequestModelDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModelDefaults(BaseModel):
    url: str
    model: str
    keyConfigured: bool


class RequestTestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection: ModelConnection | None = None


class ResponseTestModel(BaseModel):
    model: str
    elapsedMs: int


class MappingSuggestion(BaseModel):
    field: str
    role: str
    reason: str
    target: str = Field(default="", max_length=128)
    method: str = Field(default="", max_length=500)


class ResponseSuggestMapping(BaseModel):
    summary: str
    suggestions: list[MappingSuggestion]
    questions: list[str]
    qualityFindings: list[str] = Field(default_factory=list, max_length=8)
    nextChecks: list[str] = Field(default_factory=list, max_length=8)
    reportMarkdown: str = Field(default="", max_length=20000)
    toolTrace: list[str] = Field(default_factory=list, max_length=8)


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    field: str = Field(min_length=1, max_length=4096)
    role: Literal["identity", "feature", "label", "relation", "time", "ignore", "unknown"]
    target: str = Field(default="", max_length=128)
    method: str = Field(default="", max_length=500)
    reason: str = Field(default="", max_length=2000)


class RequestListPreparations(BaseModel):
    workbenchOnly: bool = False


class RequestGetPreparation(BaseModel):
    preparationId: UUID


class RequestSavePreparationReport(RequestGetPreparation):
    report: ResponseSuggestMapping


class RequestSavePreparationMapping(RequestGetPreparation):
    mapping: list[FieldMapping] = Field(min_length=1, max_length=100)
    confirmed: bool = False
    handoff: bool = False


class ResponsePreparation(BaseModel):
    id: str
    filename: str
    profile: ResponseInspectData
    report: ResponseSuggestMapping | None = None
    mapping: list[FieldMapping]
    confirmed: bool
    inWorkbench: bool
    updatedAt: datetime


class ResponseListPreparations(BaseModel):
    items: list[ResponsePreparation]
    truncated: bool


class ResponsePreparationBundle(BaseModel):
    filename: str
    contentBase64: str


class RequestSaveConversionPlan(RequestGetPreparation):
    plan: ConversionPlan


class RequestGetConversion(RequestGetPreparation):
    taskId: UUID | None = None


class RequestImportConversion(RequestGetPreparation):
    taskId: UUID
    confirm: Literal[True]


class ConversionIssue(BaseModel):
    filename: str | None = None
    path: str | None = None
    line: int
    message: str


class ConversionExample(BaseModel):
    line: int
    before: dict[str, str]
    after: dict[str, Any]


class GraphFileCoverage(BaseModel):
    filename: str
    referencedCount: int
    matchedCount: int
    missingCount: int


class GraphCoverage(BaseModel):
    referencedCount: int
    matchedCount: int
    missingCount: int
    missingIds: list[str]
    conflictCount: int
    duplicateCount: int
    files: list[GraphFileCoverage]


class ConversionReport(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    graph: GraphCoverage | None = None
    inputCount: int
    outputCount: int
    duplicateCount: int
    rejectedCount: int
    issueCount: int
    issues: list[ConversionIssue]
    examples: list[ConversionExample]
    warnings: list[str]
    passed: bool


class ResponseConversionTask(BaseModel):
    id: str
    engineVersion: str
    planVersion: str
    status: Literal["ready", "blocked", "imported"]
    sourceSha256: str
    outputSha256: str
    plan: ConversionPlan
    report: ConversionReport
    datasetId: str | None
    current: bool


class ResponseConversionState(BaseModel):
    preparationId: str
    plan: ConversionPlan | None
    planCurrent: bool
    task: ResponseConversionTask | None


class RequestDeletePreparation(RequestGetPreparation):
    confirm: Literal[True]
    revision: str = Field(min_length=64, max_length=64)


class PreparationDeletionCounts(BaseModel):
    files: int
    reports: int
    tasks: int
    datasets: int
    predictions: int
    records: dict[str, int]


class ResponsePreparationDeletion(BaseModel):
    preparationId: str
    filename: str
    revision: str
    counts: PreparationDeletionCounts
    datasetIds: list[str]
    blockedReason: str | None
    deleted: bool
