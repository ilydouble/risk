from typing import Literal

from pydantic import BaseModel

from risk_api.modules.company.api.schemas import CompanyDTO


class ShapFeature(BaseModel):
    id: str
    label: str
    category: str
    value: str
    contribution: float
    desc: str


class CommunityBenchmark(BaseModel):
    key: str
    label: str
    tag: str
    sampleSize: int
    avgScore: float
    avgDefaultProb: float
    percentile: float
    goodRate: float
    diff: float


class ScoreDetail(BaseModel):
    baseValue: int
    finalScore: int
    grade: str
    gradeNote: str
    riskPercentile: float
    defaultProb: float
    pdBase: float
    pdDelta: float
    confidence: float
    modelVersion: str
    evaluatedAt: str
    positiveCount: int
    negativeCount: int
    features: list[ShapFeature]
    benchmarks: list[CommunityBenchmark]


class RequestGetScore(BaseModel):
    companyId: str
    lang: Literal["zh", "en"] = "zh"


class ResponseGetScore(BaseModel):
    company: CompanyDTO
    detail: ScoreDetail
    demo: Literal[True] = True
