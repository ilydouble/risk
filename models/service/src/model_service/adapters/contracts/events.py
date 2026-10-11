from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Contract


class EventKind(StrEnum):
    STAGE = "stage"
    PROGRESS = "progress"
    LOG = "log"
    METRIC = "metric"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class StageEvent(Contract):
    kind: Literal[EventKind.STAGE] = EventKind.STAGE
    stage: str = Field(min_length=1, max_length=32)
    message: str = ""


class ProgressEvent(Contract):
    kind: Literal[EventKind.PROGRESS] = EventKind.PROGRESS
    current: float = Field(ge=0)
    total: float | None = Field(default=None, ge=0)
    unit: str = "items"

    @model_validator(mode="after")
    def bounded_progress(self):
        if self.total is not None and self.current > self.total:
            raise ValueError("Progress exceeds total")
        return self


class LogEvent(Contract):
    kind: Literal[EventKind.LOG] = EventKind.LOG
    level: LogLevel = LogLevel.INFO
    message: str = Field(max_length=16384)


class MetricEvent(Contract):
    kind: Literal[EventKind.METRIC] = EventKind.METRIC
    name: str = Field(min_length=1)
    value: float
    step: int | None = Field(default=None, ge=0)
    group: str | None = None
    unit: str | None = None


type AdapterEvent = Annotated[
    StageEvent | ProgressEvent | LogEvent | MetricEvent, Field(discriminator="kind")
]
