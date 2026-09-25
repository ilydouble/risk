from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risk_api.shared.api.page import Page, PageRequest


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BenchmarkCompany(BaseModel):
    id: str
    community: str
    eventCount: int
    riskProbability: float
    creditScore: int
    predictedLabel: Literal[0, 1]


class RequestSearchBenchmark(RequestBody):
    keyword: str = Field(default="", max_length=100)
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseSearchBenchmark(Page[BenchmarkCompany]):
    pass


class RequestGetBenchmark(RequestBody):
    id: str = Field(min_length=1)


class BenchmarkEvent(BaseModel):
    company: str
    cause: int
    court: int
    result: int
    age_months: float


class ResponseGetBenchmark(BenchmarkCompany):
    dataset: str
    features: dict[str, float | None]
    observedLabel: Literal[0, 1] | None
    events: list[BenchmarkEvent]


class RequestPredictBenchmark(RequestBody):
    companyIds: list[str] = Field(min_length=1, max_length=1000)


class ResponsePredictBenchmark(BaseModel):
    predictions: list[BenchmarkCompany]
    threshold: float


class RequestExplainBenchmark(RequestGetBenchmark):
    pass


class BenchmarkFeatureSensitivity(BaseModel):
    feature: str
    value: float | None
    probability_without_feature: float
    probability_delta: float


class ResponseExplainBenchmark(BaseModel):
    companyId: str
    riskProbability: float
    method: Literal["feature_occlusion_to_training_mean"]
    interpretation: str
    features: list[BenchmarkFeatureSensitivity]
    incomingEdgeCount: int


class RequestGraphBenchmark(RequestGetBenchmark):
    limit: int = Field(default=30, ge=1, le=100)


class BenchmarkGraphNode(BaseModel):
    id: str
    kind: Literal["company", "person"]
    community: str


class BenchmarkGraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: float


class ResponseGraphBenchmark(BaseModel):
    center: str
    totalEdges: int
    truncated: bool
    nodes: list[BenchmarkGraphNode]
    edges: list[BenchmarkGraphEdge]


class RequestEvaluationBenchmark(RequestBody):
    pass


class BenchmarkMetrics(BaseModel):
    n: int
    positives: int
    threshold: float
    roc_auc: float | None
    pr_auc: float | None
    ks: float | None
    brier: float
    lift_at_10pct: float | None
    capture_at_5pct: float | None
    f1: float
    precision: float
    recall: float


class ResponseEvaluationBenchmark(BaseModel):
    model: str
    mode: str
    dataset: str
    threshold: float
    metrics: dict[str, BenchmarkMetrics]
    notes: list[str]
    companyCount: int
    relationCount: int


class RequestModelCardBenchmark(RequestBody):
    pass


class ResponseModelCardBenchmark(BaseModel):
    model: str
    dataset: str
    targetDescription: str
    featureNames: list[str]
    relationNames: list[str]
    hyperedgeTypes: list[str]
    mode: str
    threshold: float
    calibrated: bool
    bestEpoch: int
    syntheticTraining: bool
    companyCount: int
