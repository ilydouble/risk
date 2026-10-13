from typing import Any, Literal

from pydantic import BaseModel, Field

from model_service.execution.contracts import RuntimeSpec
from model_service.modules.jobs.api.schemas import RequestJob


class RequestPredict(RequestJob):
    companyIds: list[str] = Field(min_length=1, max_length=32)


class PredictionDTO(BaseModel):
    fusedProbability: float | None = Field(default=None, ge=0, le=1)
    uncertainty: float | None = Field(default=None, ge=0, le=1)
    conflict: float | None = Field(default=None, ge=0, le=1)
    nodeProbability: float | None = Field(default=None, ge=0, le=1)
    graphProbability: float | None = Field(default=None, ge=0, le=1)
    companyId: str
    probability: float
    predictedLabel: int


class ResponsePredict(BaseModel):
    items: list[PredictionDTO]


class RequestCapabilities(BaseModel):
    pass


class CapabilityDTO(BaseModel):
    id: str
    name: str
    datasetFormats: list[str]
    trainable: bool
    reason: str | None


class ResponseCapabilities(BaseModel):
    items: list[CapabilityDTO]


class ResponseRuntime(BaseModel):
    runtime: RuntimeSpec


class RequestConfiguration(RequestJob):
    parameters: dict[str, Any] = Field(default_factory=dict)
    expectedDigest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ResponseConfiguration(BaseModel):
    configVersion: Literal[1]
    schemaDigest: str
    dataset: dict[str, Any]
    adapter: dict[str, Any]
    parameterSchema: dict[str, Any]
    defaultParameters: dict[str, Any]
    uiSchema: dict[str, Any]
    requestedParameters: dict[str, Any]
    resolvedParameters: dict[str, Any]
