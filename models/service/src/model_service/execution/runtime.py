"""One deployed model CLI. Its declaration is data, not an imported Python plugin."""

import json
from os import getenv
from pathlib import Path

from model_service.execution.contracts import RuntimeSpec


def model_root() -> Path:
    # Editable repository default; installed deployments set MODEL_CODE_ROOT explicitly.
    return Path(getenv("MODEL_CODE_ROOT", str(Path(__file__).resolve().parents[4])))


def runtime_spec() -> RuntimeSpec:
    return RuntimeSpec.model_validate_json((model_root() / "riskgnn/runtime.json").read_text())


def dataset_schema() -> dict:
    return json.loads((model_root() / "risk_dataset_contract.schema.json").read_text())
