from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ItemStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: ItemStatus = ItemStatus.RUNNING


class UserMessageItem(ItemBase):
    kind: Literal["user_message"] = "user_message"
    text: str = ""


class AgentReasoningItem(ItemBase):
    kind: Literal["reasoning"] = "reasoning"
    text: str = ""


class AgentMessageItem(ItemBase):
    kind: Literal["agent_message"] = "agent_message"
    text: str = ""


class ToolItem(ItemBase):
    kind: Literal["tool_call"] = "tool_call"
    toolCallId: str
    name: str
    argumentsText: str = ""
    result: JsonValue = None


Item = Annotated[
    UserMessageItem | AgentReasoningItem | AgentMessageItem | ToolItem,
    Field(discriminator="kind"),
]
