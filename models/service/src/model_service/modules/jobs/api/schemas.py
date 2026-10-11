from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objectKey: str = Field(pattern=r"^uploads/[a-zA-Z0-9-]+/[a-zA-Z0-9-]+\.zip$")


class TrainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceJobId: UUID
    runnerId: str | None = Field(default=None, min_length=1, max_length=64)
    epochs: int = Field(default=2, ge=1, le=20)


class RequestSubmitJob(BaseModel):
    jobId: UUID
    kind: Literal["validate", "train"]
    payload: ValidateInput | TrainInput

    @model_validator(mode="after")
    def matching_payload(self):
        expected = ValidateInput if self.kind == "validate" else TrainInput
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
    kind: Literal["validate", "train"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: str
    attempt: int
    cancelRequested: bool
    result: dict[str, Any]
    error: str | None
    attempts: list[AttemptDTO]


class EventDTO(BaseModel):
    sequence: int
    attempt: int
    kind: str
    data: dict[str, Any]
    createdAt: str


class ResponseEvents(BaseModel):
    items: list[EventDTO]
