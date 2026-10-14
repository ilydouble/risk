from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestDataQACatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataQAField(BaseModel):
    id: str
    name: str
    type: Literal["text", "number", "datetime", "json"]


class DataQATable(BaseModel):
    id: str
    name: str
    physicalTable: str
    fields: list[DataQAField]


class DataQADataset(BaseModel):
    id: str
    name: str


class DataQAModel(DataQADataset):
    datasetId: str


class ResponseDataQACatalog(BaseModel):
    tables: list[DataQATable]
    datasets: list[DataQADataset]
    models: list[DataQAModel]
    truncated: bool


class RequestAskData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    datasetId: UUID | None = None
    modelId: UUID | None = None

    @field_validator("question")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class ResponseAskData(BaseModel):
    question: str
    answer: str
    table: str
    columns: list[DataQAField]
    rows: list[dict[str, Any]]
    truncated: bool
    warnings: list[str]
    sql: str
    plan: dict[str, Any]
    model: str
    elapsedMs: int
    promptVersion: str
    steps: list[str]
