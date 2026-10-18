from pydantic import BaseModel, ConfigDict, Field, JsonValue

from model_service.modules.decision.contracts.prediction import (
    DecisionModelInfo,
    DecisionPrediction,
)


class RequestDecisionStatus(BaseModel):
    pass


class ResponseDecisionStatus(BaseModel):
    ready: bool
    model: DecisionModelInfo | None
    errorCode: str | None = None


class RequestDecisionPredict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict[str, JsonValue]
    expectedManifestSha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RequestDecisionPredictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapterId: str = Field(min_length=1, max_length=64)
    adapterVersion: str = Field(min_length=1, max_length=64)
    attributes: dict[str, JsonValue]
    expectedManifestSha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ResponseDecisionPredict(BaseModel):
    model: DecisionModelInfo
    prediction: DecisionPrediction
