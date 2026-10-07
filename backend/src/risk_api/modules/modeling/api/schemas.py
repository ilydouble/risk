from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from risk_api.shared.api.page import Page, PageRequest


class FileDTO(BaseModel):
    path: str
    size: int
    sha256: str


class FeatureAnalysisDTO(BaseModel):
    name: str
    kind: str
    missingCount: int
    missingRate: float
    uniqueCount: int
    constant: bool
    iv: float | None = None
    mutualInformation: float | None = None
    univariateAuc: float | None = None


class SplitAnalysisDTO(BaseModel):
    name: str
    rows: int
    positives: int
    positiveRate: float


class DriftAnalysisDTO(BaseModel):
    name: str
    split: str
    psi: float | None


class AnalysisWarningDTO(BaseModel):
    feature: str
    code: str


class CorrelationDTO(BaseModel):
    left: str
    right: str
    correlation: float


class DatasetAnalysisDTO(BaseModel):
    version: int
    scope: str
    totalRows: int
    analyzedRows: int
    duplicateSampleIds: int
    features: list[FeatureAnalysisDTO]
    splits: list[SplitAnalysisDTO]
    drift: list[DriftAnalysisDTO]
    correlations: list[CorrelationDTO]
    warnings: list[AnalysisWarningDTO]
    graph: dict[str, Any]
    driftSampleRows: dict[str, int] = Field(default_factory=dict)


class DatasetDTO(BaseModel):
    dataFormat: str | None = None
    supportedRunnerIds: list[str] = Field(default_factory=list)
    analysis: DatasetAnalysisDTO | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    id: str
    name: str
    filename: str
    size: int
    status: Literal["pending_upload", "queued", "running", "ready", "failed", "cancelled"]
    stage: str
    files: list[FileDTO]
    counts: dict[str, int]
    labeledCount: int | None = None
    positiveCount: int | None = None
    sha256: str | None = None
    error: str | None = None
    createdAt: str


class AttemptDTO(BaseModel):
    number: int
    status: str
    error: str | None
    startedAt: str
    finishedAt: str | None


class ExperimentProfileDTO(BaseModel):
    threshold: float = 0.5
    evaluationSplit: Literal["test"] = "test"
    artifactFormat: str = "riskgnn-model-v1"
    device: str = "cpu"
    version: int
    runnerId: str
    datasetFormat: str
    datasetSha256: str
    taskType: str
    target: str
    seed: int
    selectedFeatures: list[str]
    preprocessing: dict[str, Any]
    splits: dict[str, int]
    profile: str
    epochs: int
    graph: dict[str, Any]
    selectionMetric: str
    selectedEpoch: int
    codeVersion: str
    dependencies: dict[str, str]


class RunDTO(BaseModel):
    profile: ExperimentProfileDTO | None = None
    runnerId: str = "riskgnn-node-edge"
    id: str
    name: str
    datasetId: str
    retryOf: str | None
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: str
    epochs: int
    cancelRequested: bool
    attempts: list[AttemptDTO]
    result: dict[str, Any]
    error: str | None
    createdAt: str


class ModelVersionDTO(BaseModel):
    runnerId: str = "riskgnn-node-edge"
    id: str
    name: str
    runId: str
    sha256: str
    size: int
    report: dict[str, Any]
    companies: list[str]
    createdAt: str


class EventDTO(BaseModel):
    sequence: int
    attempt: int
    kind: str
    data: dict[str, Any]
    createdAt: str


class RequestCreateDatasetUpload(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"\S")
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    size: int = Field(gt=0, le=512 * 1024 * 1024)


class ResponseCreateDatasetUpload(BaseModel):
    datasetId: str
    url: str
    headers: dict[str, str]
    expiresIn: int


class RequestCompleteDatasetUpload(BaseModel):
    datasetId: UUID


class RequestGetDataset(BaseModel):
    datasetId: UUID


class ResponseGetDataset(BaseModel):
    dataset: DatasetDTO


class ResponseCompleteDatasetUpload(ResponseGetDataset):
    pass


class RequestListDatasets(BaseModel):
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseListDatasets(Page[DatasetDTO]):
    pass


class RequestCreateRun(BaseModel):
    runnerId: str = Field(default="riskgnn-node-edge", min_length=1, max_length=64)
    datasetId: UUID
    name: str = Field(min_length=1, max_length=128, pattern=r"\S")
    requestKey: UUID
    epochs: int = Field(default=2, ge=1, le=20)


class RequestGetRun(BaseModel):
    runId: UUID


class RequestCancelRun(RequestGetRun):
    pass


class RequestRerun(RequestGetRun):
    requestKey: UUID


class ResponseGetRun(BaseModel):
    run: RunDTO


class ResponseCreateRun(ResponseGetRun):
    pass


class ResponseCancelRun(ResponseGetRun):
    pass


class ResponseRerun(ResponseGetRun):
    pass


class RequestListRuns(RequestListDatasets):
    pass


class ResponseListRuns(Page[RunDTO]):
    pass


class RequestRunEvents(RequestGetRun):
    after: int = Field(default=0, ge=0)


class ResponseRunEvents(BaseModel):
    items: list[EventDTO]


class RequestPublishModel(RequestGetRun):
    name: str = Field(min_length=1, max_length=128, pattern=r"\S")


class RequestGetModel(BaseModel):
    modelId: UUID


class ResponseGetModel(BaseModel):
    model: ModelVersionDTO


class ResponsePublishModel(ResponseGetModel):
    pass


class RequestListModels(RequestListDatasets):
    pass


class ResponseListModels(Page[ModelVersionDTO]):
    pass


class RequestDownloadModel(RequestGetModel):
    pass


class ResponseDownloadModel(BaseModel):
    url: str
    sha256: str
    expiresIn: int


class RequestPredictModel(RequestGetModel):
    companyIds: list[str] = Field(min_length=1, max_length=32)


class PredictionDTO(BaseModel):
    companyId: str
    probability: float
    predictedLabel: int


class ResponsePredictModel(BaseModel):
    items: list[PredictionDTO]


class RequestModelingCapabilities(BaseModel):
    pass


class ModelCapabilityDTO(BaseModel):
    id: str
    name: str
    datasetFormats: list[str]
    trainable: bool
    reason: str | None


class ResponseModelingCapabilities(BaseModel):
    items: list[ModelCapabilityDTO]
