from typing import Literal

from pydantic import BaseModel, Field


class FinancialPredictionReference(BaseModel):
    kind: Literal["financial_prediction"] = "financial_prediction"
    predictionId: str
    modelId: str
    modelVersion: str
    manifestSha256: str
    datasetId: str
    recordId: str
    companyId: str
    companyName: str
    observationMonth: str | None
    eventScore: float = Field(ge=0, le=1)
    noEventScore: float = Field(ge=0, le=1)
    calibratedEventScore: float | None = Field(default=None, ge=0, le=1)
    target: str
    createdAt: str
    featureCount: int = Field(ge=0)
    inputSha256: str
    limitations: list[str]
