"""Typed internal-model boundary; no model implementation is imported by the backend."""

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, model_validator


class FinancialProbabilities(BaseModel):
    no_event: float = Field(ge=0, le=1)
    event: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalized(self):
        if not math.isclose(self.no_event + self.event, 1, abs_tol=1e-5):
            raise ValueError("Candidate probabilities must sum to one")
        return self


class FinancialAdapter(BaseModel):
    id: str
    version: str


class FinancialModelInfo(BaseModel):
    modelVersion: str
    manifestSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseRevision: str
    inputContractVersion: int
    inputContractSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: str
    labels: list[Literal["no_event", "event"]]
    calibrationAvailable: bool
    device: str
    dtype: str
    maxTokens: int
    supportedDatasetFormats: list[str]
    supportedAdapters: list[FinancialAdapter]


class RegisteredFinancialModel(FinancialModelInfo):
    id: str


class FinancialModelStatus(BaseModel):
    ready: bool
    model: FinancialModelInfo | None
    errorCode: str | None = None


class FinancialScore(BaseModel):
    modelVersion: str
    manifestSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expectedBaseRevision: str
    inputContractSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundleVerified: Literal[True]
    questionId: str
    target: str
    rawProbabilities: FinancialProbabilities
    calibratedProbabilities: FinancialProbabilities | None
    temperature: float | None
    device: str
    dtype: str
    inputTokensIncludingCandidates: int = Field(gt=0, le=2048)
    stateSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inferenceSeconds: float = Field(ge=0)
    providedFeatures: list[str]
    limitations: list[str]


class FinancialComputation(FinancialScore):
    inputSnapshot: dict[str, JsonValue]


class FinancialModelResult(BaseModel):
    model: FinancialModelInfo
    prediction: FinancialComputation


class FinancialSource(BaseModel):
    kind: Literal["company", "input"]
    datasetId: str | None = None
    recordId: str | None = None
    companyId: str | None = None
    companyName: str | None = None
    observationMonth: str | None = None
    snapshot: str | None = None
    label: str | None = None
    sourceSha256: str | None = None


class SavedFinancialPrediction(BaseModel):
    id: str
    model: RegisteredFinancialModel
    source: FinancialSource
    result: FinancialScore
    createdAt: datetime


class FinancialDataset(BaseModel):
    datasetId: str
    name: str
    adapterId: str
    adapterVersion: str
    recordCount: int


class FinancialCompany(BaseModel):
    recordId: str
    companyId: str
    name: str
    observationMonth: str | None
    snapshot: str
