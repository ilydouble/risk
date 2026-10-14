from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.model_connection import ModelConnection


class RequestInspectData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    contentBase64: str = Field(min_length=1, max_length=3_000_000)


class FieldProfile(BaseModel):
    name: str
    missingCount: int
    distinctCount: int
    numericRate: float
    examples: list[str]


class ResponseInspectData(BaseModel):
    sha256: str
    rowCount: int
    duplicateRows: int
    fields: list[FieldProfile]
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
