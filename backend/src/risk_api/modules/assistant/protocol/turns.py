from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from risk_api.modules.assistant.protocol.items import Item


class TurnStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class TurnError(BaseModel):
    code: str
    message: str


class Turn(BaseModel):
    id: str
    conversationId: str
    status: TurnStatus
    model: str
    requestId: str
    sequence: int
    createdAt: datetime
    finishedAt: datetime | None = None
    durationMs: int | None = Field(default=None, ge=0)
    elapsedMs: int | None = Field(default=None, ge=0)
    items: list[Item] = Field(default_factory=list)
    error: TurnError | None = None


class Conversation(BaseModel):
    id: str
    title: str
    updatedAt: datetime
