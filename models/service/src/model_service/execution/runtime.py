"""One deployed model CLI. Its declaration is data, not an imported Python plugin."""

import json

from model_service.execution.contracts import RuntimeSpec
from model_service.shared.paths import model_root as model_root


def runtime_spec() -> RuntimeSpec:
    return RuntimeSpec.model_validate_json((model_root() / "riskgnn/runtime.json").read_text())


def dataset_schema() -> dict:
    return json.loads((model_root() / "risk_dataset_contract.schema.json").read_text())
