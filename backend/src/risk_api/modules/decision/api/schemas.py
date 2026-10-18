from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from risk_api.modules.decision.contracts import (
    FinancialCompany,
    FinancialDataset,
    RegisteredFinancialModel,
    SavedFinancialPrediction,
)
from risk_api.shared.api.page import Page, PageRequest


class RequestFinancialCatalog(BaseModel):
    pass


class ResponseFinancialCatalog(BaseModel):
    ready: bool
    model: RegisteredFinancialModel | None
    datasets: list[FinancialDataset]
    errorCode: str | None = None


class RequestFinancialCompanies(BaseModel):
    datasetId: UUID
    keyword: str = Field(default="", max_length=128)
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseFinancialCompanies(Page[FinancialCompany]):
    pass


class RequestPredictFinancialCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestKey: UUID
    datasetId: UUID
    recordId: str = Field(min_length=1, max_length=512)


class RequestPreviewFinancialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requestKey: UUID
    input: dict[str, JsonValue]
    sourceLabel: str = Field(default="Explicit financial input", min_length=1, max_length=240)


class ResponsePredictFinancialCompany(BaseModel):
    prediction: SavedFinancialPrediction


class ResponsePreviewFinancialInput(BaseModel):
    prediction: SavedFinancialPrediction


class RequestGetFinancialPrediction(BaseModel):
    predictionId: UUID


class ResponseGetFinancialPrediction(BaseModel):
    prediction: SavedFinancialPrediction


class RequestListFinancialPredictions(BaseModel):
    pagination: PageRequest = Field(default_factory=PageRequest)


class ResponseListFinancialPredictions(Page[SavedFinancialPrediction]):
    pass
