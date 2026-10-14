from pydantic import BaseModel, ConfigDict, Field


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


class MappingSuggestion(BaseModel):
    field: str
    role: str
    reason: str


class ResponseSuggestMapping(BaseModel):
    summary: str
    suggestions: list[MappingSuggestion]
    questions: list[str]
