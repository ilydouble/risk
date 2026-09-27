from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class FileSpec(Contract):
    path: str = Field(min_length=1, max_length=128)
    format: Literal["csv", "parquet"]
    size_bytes: int = Field(alias="sizeBytes", gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def path_matches_format(self) -> FileSpec:
        if "/" in self.path or "\\" in self.path or self.path.startswith("."):
            raise ValueError("bundle files must be at the ZIP root")
        if not self.path.casefold().endswith(f".{self.format}"):
            raise ValueError("file extension does not match format")
        return self


class BundleFiles(Contract):
    samples: FileSpec
    nodes: FileSpec | None = None
    relations: FileSpec | None = None
    events: FileSpec | None = None
    hyperedges: FileSpec | None = None


class SampleColumns(Contract):
    sample_id: Literal["sample_id"] = Field(alias="sampleId")
    entity_id: Literal["entity_id"] = Field(alias="entityId")
    observation_time: Literal["observation_time"] = Field(alias="observationTime")
    graph_snapshot_id: Literal["graph_snapshot_id"] = Field(alias="graphSnapshotId")
    split: Literal["split"]
    target: Literal["target"]


class TargetDefinition(Contract):
    name: str = Field(min_length=1, max_length=128)
    positive_value: str | int | float = Field(alias="positiveValue")
    prediction_window_days: int | None = Field(
        default=None, alias="predictionWindowDays", ge=1
    )
    business_definition: str = Field(alias="businessDefinition", min_length=1, max_length=1000)


class FeatureDefinition(Contract):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["numeric", "categorical"]
    group: Literal[
        "application",
        "bureau",
        "financial",
        "registry",
        "judicial",
        "behavioral",
        "derived",
        "other",
    ]
    description: str = Field(default="", max_length=500)
    recommended: bool = True


class GraphDefinition(Contract):
    snapshot_mode: Literal["external"] = Field(alias="snapshotMode")
    snapshot_definition: str = Field(alias="snapshotDefinition", min_length=1, max_length=1000)
    static_experiment_only: bool = Field(default=False, alias="staticExperimentOnly")


class BundleMetadata(Contract):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    dataset_name: str = Field(alias="datasetName", min_length=1, max_length=128)
    task_type: Literal["loan_application", "entity_snapshot"] = Field(alias="taskType")
    sample_unit: Literal["loan_application", "entity_snapshot"] = Field(alias="sampleUnit")
    columns: SampleColumns
    target: TargetDefinition
    features: list[FeatureDefinition] = Field(min_length=1, max_length=500)
    files: BundleFiles
    graph: GraphDefinition | None = None

    @model_validator(mode="after")
    def validate_semantics(self) -> BundleMetadata:
        if self.task_type != self.sample_unit:
            raise ValueError("taskType and sampleUnit must match in schema v1")
        feature_names = [feature.name for feature in self.features]
        if len(feature_names) != len(set(feature_names)):
            raise ValueError("feature names must be unique")
        reserved = {
            "sample_id",
            "entity_id",
            "observation_time",
            "graph_snapshot_id",
            "split",
            "target",
        }
        if reserved.intersection(feature_names):
            raise ValueError("features cannot redefine reserved sample columns")
        graph_files = (
            self.files.nodes,
            self.files.relations,
            self.files.events,
            self.files.hyperedges,
        )
        if any(graph_files) and self.graph is None:
            raise ValueError("graph metadata is required when graph files are declared")
        paths = [spec.path for spec in self.file_specs().values()]
        if len(paths) != len(set(paths)):
            raise ValueError("bundle file paths must be unique")
        return self

    def file_specs(self) -> dict[str, FileSpec]:
        return {
            name: spec
            for name in ("samples", "nodes", "relations", "events", "hyperedges")
            if (spec := getattr(self.files, name)) is not None
        }

    def capabilities(self) -> dict[str, bool]:
        return {
            "tabular": True,
            "nodes": self.files.nodes is not None,
            "relations": self.files.relations is not None,
            "events": self.files.events is not None,
            "hyperedges": self.files.hyperedges is not None,
            "gnn": self.files.nodes is not None and self.files.relations is not None,
        }
