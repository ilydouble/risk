from typing import Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from riskgnn.dataset_adapters.contract import validate_contract
from riskgnn.dataset_adapters.contracts.common import (
    Count,
    Name,
    OutputModel,
    Sha256,
    relative_path,
)


class InspectedFile(OutputModel):
    path: Name
    size: Count
    sha256: Sha256

    _relative = field_validator("path")(relative_path)


class SplitSummary(OutputModel):
    split: Name
    count: Count
    positives: Count
    seed: Count | None = None

    @model_validator(mode="after")
    def counts(self):
        if self.positives > self.count:
            raise ValueError("Split positives exceed its sample count")
        return self


class RelationSummary(OutputModel):
    type: Name
    count: Count


class DatasetProfile(OutputModel):
    datasetFormat: Name
    taskType: Name
    target: Name
    evaluation: str | None = None
    features: list[Name] | None = None
    splits: list[SplitSummary] | None = None
    relations: list[RelationSummary] | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class InspectionResult(OutputModel):
    """Required adapter summary; specialized policy stays in the dataset adapter."""

    protocol: Name
    sha256: Sha256
    files: list[InspectedFile] = Field(min_length=1)
    counts: dict[Name, Count]
    features: list[Name] = Field(min_length=1)
    labeledCount: Count
    positiveCount: Count
    datasetProfile: DatasetProfile
    splits: list[SplitSummary]
    root: str = "."
    relations: list[RelationSummary] = Field(default_factory=list)
    analysis: dict[str, JsonValue] | None = None
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _relative = field_validator("root")(relative_path)

    @model_validator(mode="after")
    def consistency(self):
        if len(set(self.features)) != len(self.features):
            raise ValueError("Feature names must be unique")
        if len({file.path for file in self.files}) != len(self.files):
            raise ValueError("Inspected file paths must be unique")
        if "company_attr" not in self.counts:
            raise ValueError("counts.company_attr is required for enterprise export")
        if not self.positiveCount <= self.labeledCount <= self.counts["company_attr"]:
            raise ValueError("Expected positiveCount <= labeledCount <= company_attr")
        if self.datasetProfile.datasetFormat != self.protocol:
            raise ValueError("Profile format must match the inspected protocol")
        return self


class CompatibilityIssue(OutputModel):
    code: Name
    message: Name


class ValidatedDataset(InspectionResult):
    """Registry result; identity and supported runners are not chosen by the adapter."""

    datasetContract: dict[str, JsonValue]
    supportedRunnerIds: list[Name]
    compatibility: Literal["compatible", "incompatible"]
    issues: list[CompatibilityIssue]

    @field_validator("datasetContract")
    @classmethod
    def contract(cls, value):
        validate_contract(value)
        return value
