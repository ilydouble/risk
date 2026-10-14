from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ModelConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=128)
    apiKey: str = Field(default="", max_length=4096)

    @field_validator("url")
    @classmethod
    def chat_completion_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        host = parsed.hostname
        _ = parsed.port
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"/v1/chat/completions", "/chat/completions"}
        ):
            raise ValueError("Provide an HTTP(S) chat/completions endpoint without credentials")
        if host.lower() in {"localhost", "metadata.google.internal"}:
            raise ValueError("Loopback and metadata endpoints are unavailable")
        try:
            address = ip_address(host)
        except ValueError:
            pass
        else:
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_unspecified
            ):
                raise ValueError("Loopback and link-local endpoints are unavailable")
        return value


class RequestSuggestMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: ResponseInspectData
    connection: ModelConnection | None = None


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
