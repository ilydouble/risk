from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import Field, field_validator, model_validator

from .common import Contract, JsonObject
from .spec import Operation


class InspectionStatus(StrEnum):
    COMPATIBLE = "compatible"
    CONFIGURATION_REQUIRED = "configuration_required"
    INCOMPATIBLE = "incompatible"


class AssetInput(Contract):
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: str

    @field_validator("path")
    @classmethod
    def absolute_path(cls, value: Path) -> Path:
        return value.absolute()


class OperationRequest(Contract):
    operation: Operation
    inputs: dict[str, AssetInput] = Field(default_factory=dict)
    parameters: JsonObject = Field(default_factory=dict)
    configuration: JsonObject = Field(default_factory=dict)


class Artifact(Contract):
    path: str = Field(min_length=1)
    format: str = Field(min_length=1)

    @model_validator(mode="after")
    def relative_path(self):
        relative = PurePosixPath(self.path)
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in self.path
            or ":" in self.path
        ):
            raise ValueError("Artifact paths must be relative to the output directory")
        return self


class OperationResult(Contract):
    data: JsonObject = Field(default_factory=dict)
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    effective_config: JsonObject = Field(default_factory=dict)
