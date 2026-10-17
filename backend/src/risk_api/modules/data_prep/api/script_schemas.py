from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.model_connection import ModelConnection


class ResponseScriptTargetAdapter(BaseModel):
    id: str
    version: str


class ResponseScriptTarget(BaseModel):
    preset: str
    description: str
    dataset: dict[str, Any]
    adapter: ResponseScriptTargetAdapter
    config: dict[str, Any]
    requiredFiles: list[str]
    configSchema: dict[str, Any]
    guide: str
    inputSchemaCode: str


class RequestScriptCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseScriptCatalog(BaseModel):
    items: list[ResponseScriptTarget]
    runtimeImage: str


class RequestScriptFile(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    contentBase64: str = Field(min_length=1, max_length=90_000_000)


class RequestCreateScriptTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    preset: str = Field(min_length=1, max_length=128)
    datasetKey: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
    datasetVersion: str = Field(min_length=1, max_length=48)
    requirements: str = Field(default="", max_length=12000)
    files: list[RequestScriptFile] = Field(min_length=1, max_length=16)


class RequestGetScriptTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taskId: UUID


class RequestSaveScriptTask(RequestGetScriptTask):
    revision: int = Field(ge=1)
    script: str = Field(max_length=100000)
    requirements: str = Field(max_length=12000)


class RequestGenerateScript(RequestGetScriptTask):
    revision: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=12000)
    connection: ModelConnection | None = None
    maxTokens: int = Field(default=4096, ge=256, le=16384)
    runAfter: bool = False


class RequestRunScriptTask(RequestGetScriptTask):
    revision: int = Field(ge=1)


class RequestScriptArtifact(RequestGetScriptTask):
    runId: UUID


class ResponseScriptTaskSummary(BaseModel):
    id: str
    name: str
    preset: str
    revision: int
    updatedAt: datetime


class ResponseScriptTaskList(BaseModel):
    items: list[ResponseScriptTaskSummary]


class ResponseScriptInputFile(BaseModel):
    filename: str
    size: int
    sha256: str


class ResponseScriptMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    toolTrace: list[str] = Field(default_factory=list)


class ResponseScriptOutputFile(BaseModel):
    path: str
    size: int


class ResponseScriptRunResult(BaseModel):
    datasetVersion: str = ""
    files: list[ResponseScriptOutputFile] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    runtimeImage: str = ""
    exitCode: int | None = None
    deliveryDatasetId: str | None = None
    deliveryCompleted: bool = False


class ResponseScriptRun(BaseModel):
    id: str
    revision: int
    script: str
    scriptSha256: str
    status: Literal["queued", "running", "ready", "failed"]
    log: str
    error: str
    result: ResponseScriptRunResult
    artifactSha256: str | None
    createdAt: datetime
    startedAt: datetime | None
    finishedAt: datetime | None


class ResponseScriptTask(ResponseScriptTaskSummary):
    datasetKey: str
    datasetVersion: str
    sourceSha256: str
    files: list[ResponseScriptInputFile]
    requirements: str
    script: str
    messages: list[ResponseScriptMessage]
    runs: list[ResponseScriptRun]


class ResponseScriptDelivery(BaseModel):
    datasetId: str
