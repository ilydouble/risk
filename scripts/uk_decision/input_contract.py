"""Validate inference input against the contract shipped with a model version."""

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = "uk-financial-0.6b-v1"
ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "models/uk_decision/releases" / VERSION


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Question(ContractModel):
    type: Literal["choice"]
    instructions: str = Field(min_length=1)
    criteria: dict[str, str]


class OutputContract(ContractModel):
    labels: list[str]
    raw_probabilities: Literal["softmax-of-candidate-log-scores"]
    calibration: Literal["optional-binary-logit-temperature"]
    scope: Literal["matched-research-cohort"]


class InputContract(ContractModel):
    contract_version: Literal[1]
    model_version: str
    question_id: str
    question: Question
    numeric_features: list[str]
    categorical_features: list[str]
    max_tokens: int = Field(gt=0, le=2048)
    state_key: Literal["features"]
    serialization: Literal["python-json-compact-ascii-preserve-order-v1"]
    output: OutputContract

    @model_validator(mode="after")
    def validate_order(self) -> "InputContract":
        if list(self.question.criteria) != ["no_event", "event"]:
            raise ValueError("Candidate order must remain no_event, event")
        if self.output.labels != list(self.question.criteria):
            raise ValueError("Output labels must match candidate order")
        features = self.numeric_features + self.categorical_features
        if not features or len(features) != len(set(features)):
            raise ValueError("Feature names must be nonempty and unique")
        return self


def load_contract(path: Path = DEFINITION / "input-contract.json") -> InputContract:
    return InputContract.model_validate_json(path.read_bytes())


def input_state(document: dict, contract: InputContract | None = None) -> str:
    contract = contract or load_contract()
    if not isinstance(document, dict) or not isinstance(document.get("state"), dict):
        raise ValueError("Input requires a state object")
    state = document["state"]
    if set(state) != {"features"} or not isinstance(state["features"], dict):
        raise ValueError("The financial model requires state.features only")
    for name, value in state["features"].items():
        if name in contract.numeric_features:
            if not isinstance(value, (int, float, bool)) or not math.isfinite(value):
                raise ValueError(f"Invalid observed numeric feature: {name}")
        elif name in contract.categorical_features:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid observed categorical feature: {name}")
        else:
            raise ValueError(f"Feature is outside the model input allowlist: {name}")
    question = {contract.question_id: contract.question.model_dump()}
    if "questions" in document and document["questions"] != question:
        raise ValueError("Questions must match the frozen training template")
    # Preserve training serialization and key order; labels and audit IDs stay outside the prompt.
    return json.dumps(state, separators=(",", ":"), allow_nan=False)
