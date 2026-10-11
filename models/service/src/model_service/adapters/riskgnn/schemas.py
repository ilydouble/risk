"""RiskGNN-specific parameters and summaries, separate from workbench contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from model_service.adapters.contracts import InspectionStatus, JsonObject


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainParameters(Parameters):
    epochs: int = Field(default=2, ge=1, le=20)


class PredictParameters(Parameters):
    company_ids: list[str] = Field(min_length=1, max_length=32)


class InspectParameters(Parameters):
    target_operation: Literal["train"] = "train"


class InspectionIssue(Parameters):
    code: str
    message: str


class InspectionSummary(BaseModel):
    # Existing analysis/index fields are adapter-specific and remain visible.
    model_config = ConfigDict(extra="allow")
    compatibility: InspectionStatus
    issues: list[InspectionIssue]


class TrainingSummary(Parameters):
    profile: JsonObject
    companies: list[str]


class EvaluationSummary(Parameters):
    report: JsonObject


class Prediction(Parameters):
    companyId: str
    probability: float = Field(ge=0, le=1)
    predictedLabel: Literal[0, 1]


class PredictionSummary(Parameters):
    items: list[Prediction]
