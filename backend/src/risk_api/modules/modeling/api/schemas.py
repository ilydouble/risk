from typing import Literal

from pydantic import BaseModel, Field


class NumericProfileDTO(BaseModel):
    min: float
    max: float
    mean: float
    std: float


class ColumnProfileDTO(BaseModel):
    name: str
    kind: Literal["numeric", "categorical", "text"]
    missingCount: int
    missingRate: float
    uniqueCount: int
    samples: list[str]
    numeric: NumericProfileDTO | None = None


class TargetCandidateDTO(BaseModel):
    name: str
    values: list[str]


class DatasetAnalysisDTO(BaseModel):
    rowCount: int
    columnCount: int
    missingCells: int
    missingRate: float
    duplicateRows: int
    numericColumnCount: int
    categoricalColumnCount: int
    columns: list[ColumnProfileDTO]
    targetCandidates: list[TargetCandidateDTO]
    warnings: list[str]


class DatasetDTO(BaseModel):
    id: str
    name: str
    filename: str
    contentType: str
    size: int
    status: Literal["pending", "ready", "failed"]
    rowCount: int | None
    columnCount: int | None
    analysis: DatasetAnalysisDTO | None
    preview: list[dict[str, str]] | None
    error: str | None
    createdAt: str


class RequestCreateDatasetUpload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    size: int = Field(gt=0, le=5_000_000)


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


class ConfusionMatrixDTO(BaseModel):
    tp: int
    fp: int
    tn: int
    fn: int


class CalibrationBinDTO(BaseModel):
    lower: float
    count: int
    meanPrediction: float
    observedRate: float


class MetricSetDTO(BaseModel):
    rows: int
    positives: int
    rocAuc: float
    prAuc: float
    ks: float
    brier: float
    precision: float
    recall: float
    f1: float
    threshold: float
    confusion: ConfusionMatrixDTO
    calibration: list[CalibrationBinDTO]


class ExperimentMetricsDTO(BaseModel):
    train: MetricSetDTO
    test: MetricSetDTO


class CoefficientDTO(BaseModel):
    feature: str
    coefficient: float


class ExperimentConfigurationDTO(BaseModel):
    seed: int
    split: str
    evaluationScope: str
    trainRows: int
    testRows: int
    negativeValue: str


class ExperimentDTO(BaseModel):
    id: str
    datasetId: str
    name: str
    modelType: Literal["logistic_regression"]
    status: Literal["completed"]
    targetColumn: str
    positiveValue: str
    featureColumns: list[str]
    configuration: ExperimentConfigurationDTO
    metrics: ExperimentMetricsDTO
    coefficients: list[CoefficientDTO]
    createdAt: str


class RequestRunExperiment(BaseModel):
    datasetId: str
    name: str = Field(min_length=1, max_length=128)
    modelType: Literal["logistic_regression"] = "logistic_regression"
    targetColumn: str = Field(min_length=1, max_length=255)
    positiveValue: str = Field(max_length=255)
    featureColumns: list[str] = Field(min_length=1, max_length=20)
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
