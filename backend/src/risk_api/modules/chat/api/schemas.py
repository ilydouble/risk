from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from risk_api.shared.api.model_connection import ModelConnection


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)

    @field_validator("content")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class RequestChat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    connection: ModelConnection | None = None
    maxTokens: int = Field(default=4096, ge=256, le=16384)

    @field_validator("messages")
    @classmethod
    def conversation(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if value[-1].role != "user" or sum(len(m.content) for m in value) > 32000:
            raise ValueError("Invalid conversation or conversation too long")
        return value


class ResponseChat(BaseModel):
    content: str
    model: str
    elapsedMs: int
