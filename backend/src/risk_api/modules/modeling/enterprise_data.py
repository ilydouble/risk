"""Versioned interchange records, independent of HTTP and model dependencies."""

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FORMAT = "risk-enterprise-data-v1"
MAX_BYTES = 4 * 1024 * 1024 * 1024
MAX_LINE = 16 * 1024 * 1024


class NormalizedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    kind: Literal["company", "person", "edge", "hyperedge", "event"]
    snapshot: str = Field(min_length=1, max_length=256)
    nodeId: str | None = Field(default=None, min_length=1, max_length=512)
    source: str | None = Field(default=None, min_length=1, max_length=512)
    target: str | None = Field(default=None, min_length=1, max_length=512)
    members: list[str] = Field(default_factory=list)
    data: dict[str, Any]

    @model_validator(mode="after")
    def structure(self):
        if self.kind in {"company", "person"}:
            if not self.nodeId or self.source or self.target or self.members:
                raise ValueError("Invalid node identity")
            attrs = self.data.get("attributes")
            if not isinstance(attrs, dict):
                raise ValueError("Node attributes must be a mapping")
        elif self.nodeId:
            raise ValueError("Only nodes have nodeId")
        if self.kind in {"edge", "event"} and self.members:
            raise ValueError("Only hyperedges have members")
        if self.kind == "event" and self.target:
            raise ValueError("Events have one company reference")
        if self.kind == "hyperedge" and (self.source or self.target):
            raise ValueError("Hyperedges use member references")
        if self.kind == "edge" and (not self.source or not self.target):
            raise ValueError("Edge endpoints are required")
        if self.kind == "event" and not self.source:
            raise ValueError("Event company is required")
        if self.kind == "hyperedge" and (
            not self.members or len(set(self.members)) != len(self.members)
        ):
            raise ValueError("Invalid hyperedge members")
        return self


def records(path: Path):
    with path.open(encoding="utf-8") as stream:
        sequence = 0
        while line := stream.readline(MAX_LINE + 1):
            if len(line.encode("utf-8")) > MAX_LINE:
                raise ValueError("Enterprise record exceeds size limit")
            value = json.loads(line, parse_constant=reject_constant, parse_float=finite_float)
            if not isinstance(value, dict):
                raise ValueError("Enterprise records must be JSON objects")
            if sequence == 0:
                if value.get("format") != FORMAT:
                    raise ValueError("Unsupported enterprise data format")
                yield sequence, value
            else:
                yield sequence, NormalizedRecord.model_validate(value)
            sequence += 1
        if not sequence:
            raise ValueError("Empty enterprise data")


def reject_constant(value: str):
    raise ValueError(f"Invalid JSON number: {value}")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Invalid JSON number")
    return number
