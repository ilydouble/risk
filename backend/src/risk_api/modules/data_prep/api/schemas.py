from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.model_connection import ModelConnection


class RequestInspectData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    contentBase64: str = Field(min_length=1, max_length=3_000_000)


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


class ResponseSuggestMapping(BaseModel):
    summary: str
    suggestions: list[MappingSuggestion]
    questions: list[str]
    qualityFindings: list[str] = Field(default_factory=list, max_length=8)
    nextChecks: list[str] = Field(default_factory=list, max_length=8)
