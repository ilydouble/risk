from __future__ import annotations

import sys
from os import getenv
from typing import Any, Literal

import pandas as pd
import sklearn
import torch
from pydantic import BaseModel, ConfigDict, Field

from workbench.data import BundleData
from workbench.tabular import TabularSuite


class ProfileContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DatasetProfile(ProfileContract):
    dataset_name: str = Field(alias="datasetName")
    bundle_schema_version: int = Field(alias="bundleSchemaVersion")
    bundle_sha256: str = Field(alias="bundleSha256", pattern=r"^[0-9a-f]{64}$")
    task_type: Literal["loan_application", "entity_snapshot"] = Field(alias="taskType")
    sample_unit: Literal["loan_application", "entity_snapshot"] = Field(alias="sampleUnit")
    sample_count: int = Field(alias="sampleCount", ge=1)
    entity_count: int = Field(alias="entityCount", ge=1)
    graph_snapshot_count: int = Field(alias="graphSnapshotCount", ge=1)
    files: dict[str, dict[str, Any]]


class TargetProfile(ProfileContract):
    name: str
    positive_value: str | int | float = Field(alias="positiveValue")
    prediction_window_days: int | None = Field(alias="predictionWindowDays")
    business_definition: str = Field(alias="businessDefinition")


class FeatureProfile(ProfileContract):
    selection_mode: str = Field(alias="selectionMode")
    fit_split: Literal["train"] = Field(alias="fitSplit")
    selected: list[dict[str, Any]]
    excluded: list[dict[str, str]]
    rules: dict[str, Any]


class EncodingProfile(ProfileContract):
    numeric: dict[str, Any]
    categorical: dict[str, Any]
    nodes: dict[str, Any]
    events: dict[str, Any]


class GraphProfile(ProfileContract):
    enabled: bool
    snapshot_definition: str | None = Field(alias="snapshotDefinition")
    static_experiment_only: bool = Field(alias="staticExperimentOnly")
    nodes: dict[str, Any]
    relations: dict[str, Any]
    events: dict[str, Any]
    hyperedges: dict[str, Any]


class TrainingProfileConfig(ProfileContract):
    seed: int
    requested_runs: list[str] = Field(alias="requestedRuns")
    riskgnn: dict[str, Any]
    protocol: dict[str, Any]


class EvaluationProfile(ProfileContract):
    validation_role: str = Field(alias="validationRole")
    final_split: Literal["test"] = Field(alias="finalSplit")
    variants: list[dict[str, Any]]


class ProvenanceProfile(ProfileContract):
    core_implementation: str = Field(alias="coreImplementation")
    artifact_format: str = Field(alias="artifactFormat")
    python_version: str = Field(alias="pythonVersion")
    torch_version: str = Field(alias="torchVersion")
    sklearn_version: str = Field(alias="sklearnVersion")
    code_version: str = Field(alias="codeVersion")


class TrainingProfile(ProfileContract):
    profile_version: Literal[1] = Field(default=1, alias="profileVersion")
    model_family: Literal["RiskGNN-v1"] = Field(default="RiskGNN-v1", alias="modelFamily")
    dataset_id: str = Field(alias="datasetId")
    experiment_id: str = Field(alias="experimentId")
    dataset: DatasetProfile
    target: TargetProfile
    splits: dict[str, dict[str, Any]]
    features: FeatureProfile
    encoding: EncodingProfile
    graph: GraphProfile
    training: TrainingProfileConfig
    evaluation: EvaluationProfile
    provenance: ProvenanceProfile
    limitations: list[str]


def _split_profile(data: BundleData) -> dict[str, dict[str, Any]]:
    positive = str(data.metadata.target.positive_value)
    result = {}
    for name, rows in data.samples.groupby("split"):
        target = rows["target"].astype(str) == positive
        result[str(name)] = {
            "rows": len(rows),
            "positives": int(target.sum()),
            "positiveRate": float(target.mean()),
            "entities": int(rows["entity_id"].astype(str).nunique()),
        }
    return result


def _count(frame: pd.DataFrame | None) -> int:
    return 0 if frame is None else len(frame)


def _values(frame: pd.DataFrame | None, column: str) -> list[str]:
    if frame is None or column not in frame:
        return []
    return sorted(set(frame[column].dropna().astype(str)))


def build_training_profile(
    data: BundleData,
    request: dict[str, Any],
    suite: TabularSuite,
    *,
    bundle_sha256: str,
    dataset_id: str,
    experiment_id: str,
) -> TrainingProfile:
    metadata = data.metadata
    declared = {feature.name: feature for feature in metadata.features}
    selected = [
        declared[name].model_dump(mode="json", by_alias=True) for name in suite.selection.selected
    ]
    graph = metadata.graph
    hyperedge_count = (
        0
        if data.hyperedges is None
        else len(
            data.hyperedges[["graph_snapshot_id", "hyperedge_id"]].astype(str).drop_duplicates()
        )
    )
    configuration = request["configuration"]
    variants = [
        {
            "name": variant.name,
            "role": variant.result["role"],
            "configuration": variant.result.get("configuration", {}),
            "durationSeconds": variant.result.get("durationSeconds"),
            "validation": variant.result["metrics"]["validation"],
            "test": variant.result["metrics"]["test"],
        }
        for variant in suite.variants
    ]
    limitations = []
    if graph and graph.static_experiment_only:
        limitations.append("static_graph_not_strict_future_prediction")
    if metadata.task_type == "entity_snapshot":
        limitations.append("entity_risk_not_loan_default_probability")
    profile = TrainingProfile(
        datasetId=dataset_id,
        experimentId=experiment_id,
        dataset=DatasetProfile(
            datasetName=metadata.dataset_name,
            bundleSchemaVersion=metadata.schema_version,
            bundleSha256=bundle_sha256,
            taskType=metadata.task_type,
            sampleUnit=metadata.sample_unit,
            sampleCount=len(data.samples),
            entityCount=int(data.samples["entity_id"].astype(str).nunique()),
            graphSnapshotCount=int(data.samples["graph_snapshot_id"].astype(str).nunique()),
            files={
                name: spec.model_dump(mode="json", by_alias=True)
                for name, spec in metadata.file_specs().items()
            },
        ),
        target=TargetProfile(
            name=metadata.target.name,
            positiveValue=metadata.target.positive_value,
            predictionWindowDays=metadata.target.prediction_window_days,
            businessDefinition=metadata.target.business_definition,
        ),
        splits=_split_profile(data),
        features=FeatureProfile(
            selectionMode=str(configuration["featureMode"]),
            fitSplit="train",
            selected=selected,
            excluded=suite.selection.excluded,
            rules=suite.selection.configuration,
        ),
        encoding=EncodingProfile(
            numeric={
                "fitSplit": "train",
                "imputation": "median",
                "scaling": "standard",
                "clip": [-10, 10],
                "missingIndicator": True,
            },
            categorical={
                "fitSplit": "train",
                "unknownIndex": 0,
                "embeddingDimension": 8,
                "initialization": "random",
                "vocabularyPersistedInArtifact": True,
            },
            nodes={
                "enabled": data.nodes is not None,
                "schemaSource": "nodes_table",
                "numericInferenceThreshold": 0.9,
                "typeVocabularyFitSplit": "train_entities",
            },
            events={
                "enabled": bool(configuration["useEvents"] and data.events is not None),
                "typeEmbeddingDimension": 8,
                "amountTransform": "log1p_train_standard",
                "timeDecay": "exponential_365_day_half_life",
            },
        ),
        graph=GraphProfile(
            enabled=bool(data.nodes is not None and data.relations is not None),
            snapshotDefinition=graph.snapshot_definition if graph else None,
            staticExperimentOnly=bool(graph and graph.static_experiment_only),
            nodes={"rows": _count(data.nodes), "types": _values(data.nodes, "node_type")},
            relations={
                "rows": _count(data.relations),
                "types": _values(data.relations, "relation_type"),
                "reverseTypesAdded": data.relations is not None,
                "positiveWeightsRequired": True,
            },
            events={"rows": _count(data.events), "types": _values(data.events, "event_type")},
            hyperedges={
                "membershipRows": _count(data.hyperedges),
                "count": hyperedge_count,
                "types": _values(data.hyperedges, "hyperedge_type"),
            },
        ),
        training=TrainingProfileConfig(
            seed=int(configuration["seed"]),
            requestedRuns=list(request["requested_models"]),
            riskgnn={
                "core": "RiskGNNCore",
                "hiddenDimension": 32,
                "relationLayers": 2,
                "dropout": 0.1,
                "optimizer": "AdamW",
                "learningRate": 0.01,
                "weightDecay": 0.0001,
                "loss": "class_weighted_binary_cross_entropy",
                "maxEpochs": 80,
                "earlyStoppingPatience": 12,
                "eventsEnabled": bool(configuration["useEvents"]),
                "relationsEnabled": bool(configuration["useRelations"]),
                "hyperedgesEnabled": bool(configuration["useHyperedges"]),
            },
            protocol={
                "trainingScope": "current_dataset_only",
                "weightsTransferred": False,
                "externalPretrainedEmbeddings": False,
                "embeddingInitialization": "random",
                "preprocessingFitSplit": "train",
                "earlyStoppingSplit": "validation",
                "testUsedForSelection": False,
            },
        ),
        evaluation=EvaluationProfile(
            validationRole="early_stopping_and_threshold_selection",
            finalSplit="test",
            variants=variants,
        ),
        provenance=ProvenanceProfile(
            coreImplementation="com_risk_runtime.model.RiskGNNCore",
            artifactFormat="workbench-experiment-v2",
            pythonVersion=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            torchVersion=str(torch.__version__),
            sklearnVersion=str(sklearn.__version__),
            codeVersion=getenv("RISK_MODEL_CODE_VERSION", "workspace-unversioned"),
        ),
        limitations=limitations,
    )
    return profile
