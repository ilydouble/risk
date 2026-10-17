from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from risk_api.modules.assistant.protocol.events import TurnEvent
from risk_api.modules.assistant.protocol.turns import Conversation, Turn
from risk_api.shared.api.model_connection import ModelConnection


class RequestListConversations(BaseModel):
    pass


class RequestCreateConversation(BaseModel):
    pass


class RequestGetConversation(BaseModel):
    conversationId: UUID


class RequestCreateTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    conversationId: UUID
    requestKey: UUID
    message: str = Field(min_length=1, max_length=8000)
    connection: ModelConnection | None = None
    lang: Literal["zh", "en"] = "zh"
    maxTokens: int = Field(default=4096, ge=256, le=16384)


class RequestCancelTurn(BaseModel):
    turnId: UUID


class RequestTurnEvents(BaseModel):
    turnId: UUID
    afterSequence: int = Field(default=0, ge=0)


class ResponseListConversations(BaseModel):
    conversations: list[Conversation]


class ResponseCreateConversation(BaseModel):
    conversation: Conversation


class ResponseGetConversation(BaseModel):
    turns: list[Turn]


class ResponseCreateTurn(BaseModel):
    turn: Turn


class ResponseCancelTurn(BaseModel):
    turn: Turn


# SSE data is a protocol object, not an ApiEnvelope. This DTO publishes its schema for generation.
class ResponseTurnEvent(TurnEvent):
    pass


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
