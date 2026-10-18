"""Financial scoring output shared by CLI and HTTP."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue


class Probabilities(BaseModel):
    no_event: float = Field(ge=0, le=1)
    event: float = Field(ge=0, le=1)


class SupportedAdapter(BaseModel):
    id: str
    version: str


class DecisionModelInfo(BaseModel):
    modelVersion: str
    manifestSha256: str
    baseRevision: str
    inputContractVersion: int
    inputContractSha256: str
    target: str
    labels: list[str]
    calibrationAvailable: bool
    device: str
    dtype: str
    maxTokens: int
    supportedDatasetFormats: list[str] = ["uk-research-v2", "uk-financial-jsonl-v1"]
    supportedAdapters: list[SupportedAdapter] = [
        SupportedAdapter(id="uk-dataset-v1", version="2"),
        SupportedAdapter(id="uk-financial-jsonl", version="1"),
    ]


class DecisionPrediction(BaseModel):
    model: str = "Qwen3-0.6B UK financial LoRA"
    modelVersion: str
    manifestSha256: str
    expectedBaseRevision: str
    baseConfigSha256: str
    inputContractSha256: str
    bundleVerified: bool
    device: str
    dtype: str
    scoringMode: Literal["tree"] = "tree"
    questionId: str
    target: str
    rawProbabilities: Probabilities
    calibratedProbabilities: Probabilities | None
    temperature: float | None
    inputTokensIncludingCandidates: int
    stateSha256: str
    adapterSha256: str
    runtimeSha256: str
    loadSeconds: float
    inferenceSeconds: float
    peakAllocatedMiB: float | None
    inputSnapshot: dict[str, JsonValue]
    providedFeatures: list[str]
    limitations: list[str]
