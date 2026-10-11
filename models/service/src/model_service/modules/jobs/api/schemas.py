from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from model_service.modules.jobs.operations import ExecuteInput


class ValidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objectKey: str = Field(pattern=r"^uploads/[a-zA-Z0-9-]+/[a-zA-Z0-9-]+\.zip$")


class TrainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceJobId: UUID
    runnerId: Literal["riskgnn"] = "riskgnn"
    configuration: dict[str, Any] | None = None
    # Already queued legacy jobs remain executable; new submissions carry a frozen snapshot.
    epochs: int | None = Field(default=None, ge=1, le=20)


class RequestSubmitJob(BaseModel):
    jobId: UUID
    kind: Literal["validate", "train", "execute"]
    payload: ValidateInput | TrainInput | ExecuteInput

    @model_validator(mode="after")
    def matching_payload(self):
        expected = {"validate": ValidateInput, "train": TrainInput, "execute": ExecuteInput}[
            self.kind
        ]
        if not isinstance(self.payload, expected):
            raise ValueError("Payload does not match job kind")
        return self


class RequestJob(BaseModel):
    jobId: UUID


class RequestEvents(RequestJob):
    after: int = Field(default=0, ge=0)


class AttemptDTO(BaseModel):
    number: int
    status: str
    error: str | None
    startedAt: str
    finishedAt: str | None


class ResponseJob(BaseModel):
    id: str
    kind: Literal["validate", "train", "execute"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: str
    attempt: int
    cancelRequested: bool
    result: dict[str, Any]
    error: str | None
    attempts: list[AttemptDTO]


class ExecutionEventKind(StrEnum):
    STATE = "state"
    STAGE = "stage"
    PROGRESS = "progress"
    LOG = "log"
    METRIC = "metric"


class EventDTO(BaseModel):
    sequence: int
    attempt: int
    kind: ExecutionEventKind
    data: dict[str, Any]
    createdAt: str


class ResponseEvents(BaseModel):
    items: list[EventDTO]
