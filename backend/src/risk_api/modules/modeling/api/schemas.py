from typing import Any, Literal

from pydantic import BaseModel, Field

ModelName = Literal[
    "logistic_regression",
    "hist_gradient_boosting",
    "graph_stats_hgb",
    "gnn_self_only",
    "gnn_no_hyper",
    "gnn_full",
]


class DatasetDTO(BaseModel):
    id: str
    name: str
    filename: str
    contentType: str
    size: int
    schemaVersion: int
    taskType: Literal["loan_application", "entity_snapshot", "legacy_tabular"] | None
    sampleUnit: Literal["loan_application", "entity_snapshot"] | None
    status: Literal["pending_upload", "queued", "running", "ready", "failed", "legacy"]
    rowCount: int | None
    columnCount: int | None
    manifest: dict[str, Any] | None
    capabilities: dict[str, Any]
    analysis: dict[str, Any] | None
    validation: dict[str, Any]
    progress: dict[str, Any]
    error: str | None
    createdAt: str
    startedAt: str | None
    finishedAt: str | None


class RequestCreateDatasetUpload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    size: int = Field(gt=0, le=512 * 1024 * 1024)


class ResponseCreateDatasetUpload(BaseModel):
    datasetId: str
    url: str
    headers: dict[str, str]
    expiresIn: int = 60


class RequestCompleteDatasetUpload(BaseModel):
    datasetId: str


class ResponseCompleteDatasetUpload(BaseModel):
    dataset: DatasetDTO


class RequestListDatasets(BaseModel):
    pass


class ResponseListDatasets(BaseModel):
    items: list[DatasetDTO]


class RequestGetDataset(BaseModel):
    datasetId: str


class ResponseGetDataset(BaseModel):
    dataset: DatasetDTO


class ExperimentDTO(BaseModel):
    id: str
    datasetId: str
    name: str
    modelType: Literal["comparison_suite", "logistic_regression"]
    status: Literal["queued", "running", "completed", "failed"]
    targetName: str | None
    positiveValue: str
    featureColumns: list[str]
    selectedFeatures: list[str]
    requestedModels: list[str]
    configuration: dict[str, Any]
    progress: dict[str, Any]
    results: dict[str, Any]
    artifacts: dict[str, Any]
    error: str | None
    createdAt: str
    startedAt: str | None
    finishedAt: str | None


class RequestRunExperiment(BaseModel):
    datasetId: str
    name: str = Field(min_length=1, max_length=128)
    targetName: str = Field(min_length=1, max_length=128)
    featureMode: Literal["recommended", "manual"] = "recommended"
    featureColumns: list[str] = Field(default_factory=list, max_length=200)
    models: list[ModelName] = Field(min_length=1, max_length=6)
    useEvents: bool = True
    useRelations: bool = True
    useHyperedges: bool = True
    enableGnnAblations: bool = True
    seed: int = Field(default=42, ge=0, le=2_147_483_647)


class ResponseRunExperiment(BaseModel):
    experiment: ExperimentDTO


class RequestListExperiments(BaseModel):
    pass


class ResponseListExperiments(BaseModel):
    items: list[ExperimentDTO]


class RequestGetExperiment(BaseModel):
    experimentId: str


class ResponseGetExperiment(BaseModel):
    experiment: ExperimentDTO
