from typing import Final, Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from riskgnn.dataset_adapters.contract import validate_contract
from riskgnn.dataset_adapters.contracts.common import Count, Name, OutputModel, Sha256

FORMAT: Final = "risk-enterprise-data-v1"
MAX_BYTES = 512 * 1024 * 1024
MAX_LINE = 1024 * 1024
RecordKind = Literal["company", "person", "edge", "hyperedge", "event"]


class EnterpriseNodeData(OutputModel):
    attributes: dict[Name, int | float | None]
    name: str | None = None
    label: Literal[0, 1] | None = None
    community: str | None = None
    split: str | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    sourceRecord: dict[str, JsonValue] | None = None


class EnterpriseRecord(OutputModel):
    kind: RecordKind
    snapshot: str = Field(min_length=1, max_length=256)
    nodeId: str | None = Field(default=None, min_length=1, max_length=512)
    source: str | None = Field(default=None, min_length=1, max_length=512)
    target: str | None = Field(default=None, min_length=1, max_length=512)
    members: list[Name] = Field(default_factory=list)
    data: dict[str, JsonValue]

    @model_validator(mode="after")
    def structure(self):
        if self.kind in {"company", "person"}:
            if not self.nodeId or self.source or self.target or self.members:
                raise ValueError("Invalid node identity")
            if not isinstance(self.data.get("attributes"), dict):
                raise ValueError("Node attributes must be a mapping")
            EnterpriseNodeData.model_validate(self.data)
            label = self.data.get("label")
            if label is not None and (type(label) is not int or label not in (0, 1)):
                raise ValueError("Node label must be 0, 1 or null")
        elif self.nodeId:
            raise ValueError("Only nodes have nodeId")
        if self.kind in {"edge", "event"} and self.members:
            raise ValueError("Only hyperedges have members")
        if self.kind == "edge" and (not self.source or not self.target):
            raise ValueError("Edge endpoints are required")
        if self.kind == "event" and (not self.source or self.target):
            raise ValueError("Events have one company reference")
        if self.kind == "hyperedge" and (
            self.source or self.target or not self.members
            or len(set(self.members)) != len(self.members)
        ):
            raise ValueError("Hyperedges require unique member references")
        return self


class EnterpriseManifest(OutputModel):
    format: Literal["risk-enterprise-data-v1"] = FORMAT
    datasetContract: dict[str, JsonValue]
    sourceSha256: Sha256
    featureNames: list[Name] = Field(min_length=1)
    target: Name

    @field_validator("featureNames")
    @classmethod
    def unique_features(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Feature names must be unique")
        return value

    @field_validator("datasetContract")
    @classmethod
    def contract(cls, value):
        validate_contract(value)
        return value


class EnterpriseExportSummary(OutputModel):
    format: Literal["risk-enterprise-data-v1"] = FORMAT
    counts: dict[RecordKind, Count]
