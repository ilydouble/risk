from pydantic import BaseModel, Field

from model_service.modules.jobs.api.schemas import RequestJob


class RequestPredict(RequestJob):
    companyIds: list[str] = Field(min_length=1, max_length=32)


class PredictionDTO(BaseModel):
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
