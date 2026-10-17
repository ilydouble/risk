"""Model-owned experiment configuration; dataset identity and splits stay immutable."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from riskgnn.dataset_adapters.contract import validate_contract
from riskgnn.dataset_adapters.delivery import delivery_for


class ConfigurationError(ValueError):
    def __init__(self, message: str, *, stale: bool = False):
        super().__init__(message)
        self.stale = stale


def merge(base: dict, overrides: dict) -> dict:
    result = deepcopy(base)
    for key, value in overrides.items():
        result[key] = (
            merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else deepcopy(value)
        )
    return result


def validate_parameters(schema: dict, parameters: dict) -> None:
    try:
        Draft202012Validator(schema).validate(parameters)
    except ValidationError as error:
        path = ".".join(map(str, error.absolute_path)) or "parameters"
        raise ConfigurationError(f"{path}: {error.message}") from error


def descriptor_digest(configuration: dict) -> str:
    descriptor = {
        key: value
        for key, value in configuration.items()
        if key not in {"schemaDigest", "requestedParameters", "resolvedParameters"}
    }
    return hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def describe(contract: dict) -> dict:
    validate_contract(contract)
    identity = contract["adapter"]
    delivery = delivery_for(identity["id"], identity["version"])
    operation = json.loads((Path(__file__).resolve().parents[1] / "runtime.json").read_text())[
        "operations"
    ]["train"]
    schema = deepcopy(operation["parameters_schema"])
    dataset_schema = deepcopy(delivery.config_schema)
    # All resolved keys must be explicit, so later defaults cannot alter a queued run.
    defaults = merge(
        operation["default_parameters"],
        {
            "dataset": delivery.config(identity["config"]),
        },
    )
    adaptive_uk = identity["id"] == "uk-dataset-v1" and identity["version"] == "2"
    if adaptive_uk:
        schema["properties"]["fusion"] = {
            "type": "string",
            "enum": ["legacy", "adaptive"],
            "default": "adaptive",
        }
        defaults["fusion"] = "adaptive"
    else:
        schema["properties"].pop("fusion", None)
    dataset_schema["required"] = sorted(defaults["dataset"])
    schema["properties"]["dataset"] = dataset_schema
    schema["required"] = sorted(defaults)
    descriptor = {
        "configVersion": 1,
        "dataset": deepcopy(contract["dataset"]),
        "adapter": {"id": identity["id"], "version": identity["version"]},
        "parameterSchema": schema,
        "defaultParameters": defaults,
        "uiSchema": deepcopy(operation["ui_schema"]),
    }
    if adaptive_uk:
        descriptor["uiSchema"]["fields"].append(
            {
                "path": "fusion",
                "label": {"zh": "分支融合", "en": "Branch fusion"},
                "description": {
                    "zh": "adaptive按观察门控并处理缺失；legacy保留历史全局融合。",
                    "en": "Adaptive missing-aware gating or legacy global fusion.",
                },
            }
        )
    descriptor["schemaDigest"] = descriptor_digest(descriptor)
    return descriptor


def resolve(contract: dict, requested: dict, expected_digest: str | None = None) -> dict:
    descriptor = describe(contract)
    if expected_digest is not None and expected_digest != descriptor["schemaDigest"]:
        raise ConfigurationError("Configuration declaration changed; reload the form", stale=True)
    resolved = merge(descriptor["defaultParameters"], requested)
    validate_parameters(descriptor["parameterSchema"], resolved)
    return {
        **descriptor,
        "requestedParameters": deepcopy(requested),
        "resolvedParameters": resolved,
    }


def validate_frozen(contract: dict, parameters: dict, snapshot: dict) -> dict:
    current = describe(contract)
    if snapshot.get("configVersion") != 1:
        raise ConfigurationError("Unsupported experiment configuration version")
    if any(snapshot.get(key) != current[key] for key in ("dataset", "adapter")):
        raise ConfigurationError("Configuration belongs to a different dataset or adapter")
    if descriptor_digest(snapshot) != snapshot.get("schemaDigest"):
        raise ConfigurationError("Configuration declaration checksum mismatch")
    resolved = snapshot["resolvedParameters"]
    if (
        parameters != resolved
        or merge(snapshot["defaultParameters"], snapshot["requestedParameters"]) != resolved
    ):
        raise ConfigurationError("Execution parameters differ from the frozen configuration")
    # Validate compatibility with current code, but never apply its new defaults on retry.
    if resolved.get("algorithm") != "riskgnn-plus":
        raise ConfigurationError(
            "This experiment uses the previous RiskGNN runtime; create a new RiskGNN+ experiment",
            stale=True,
        )
    current_schema = deepcopy(current["parameterSchema"])
    if "fusion" not in snapshot["defaultParameters"]:
        # Old frozen UK runs retain legacy fusion instead of adopting a new default.
        current_schema["required"] = [k for k in current_schema["required"] if k != "fusion"]
    validate_parameters(current_schema, resolved)
    validate_parameters(snapshot["parameterSchema"], resolved)
    return deepcopy(snapshot)
