from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from risk_api.modules.assistant.protocol.items import Item
from risk_api.modules.assistant.protocol.turns import TurnError, TurnStatus


class EventType(StrEnum):
    TURN_STARTED = "turn_started"
    ITEM_UPDATED = "item_updated"
    ITEM_DELTA = "item_delta"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_CANCELLED = "turn_cancelled"
    TURN_INTERRUPTED = "turn_interrupted"


class ItemDelta(BaseModel):
    itemId: str
    field: Literal["text", "argumentsText"]
    text: str


class TurnEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    turnId: str
    sequence: int
    type: EventType
    item: Item | None = None
    delta: ItemDelta | None = None
    status: TurnStatus | None = None
    error: TurnError | None = None
