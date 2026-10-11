from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import Contract, JsonObject


class Operation(StrEnum):
    INSPECT = "inspect"
    TRAIN = "train"
    EVALUATE = "evaluate"
    PREDICT = "predict"


class InputSpec(Contract):
    kind: Literal["file", "directory"]
    formats: list[str] = Field(default_factory=list)
    required: bool = True


class ArtifactSpec(Contract):
    format: str = Field(min_length=1)
    kind: Literal["file", "directory"]
    required: bool = True


def _object_schema() -> JsonObject:
    return {"type": "object"}


class OperationSpec(Contract):
    inputs: dict[str, InputSpec] = Field(default_factory=dict)
    parameters_schema: JsonObject = Field(default_factory=_object_schema)
    default_parameters: JsonObject = Field(default_factory=dict)
    result_schema: JsonObject = Field(default_factory=_object_schema)
    artifacts: dict[str, ArtifactSpec] = Field(default_factory=dict)
    ui_schema: JsonObject = Field(default_factory=dict)


class RuntimeSpec(Contract):
    runtime_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    runtime_version: str = Field(min_length=1, max_length=64)
    contract_version: Literal[2] = 2
    name: str
    description: str = ""
    operations: dict[Operation, OperationSpec]
