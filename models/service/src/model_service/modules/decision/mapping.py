"""Convert declared UK source records; never infer financial values from graph features."""

import math

from model_service.modules.decision.contracts.input import InputContract
from model_service.modules.decision.errors import DecisionError


def record_input(
    adapter_id: str, adapter_version: str, attributes: dict, contract: InputContract
) -> tuple[dict, list[str]]:
    if (adapter_id, adapter_version) not in {("uk-dataset-v1", "2"), ("uk-financial-jsonl", "1")}:
        raise DecisionError(
            422,
            "DECISION_DATASET_UNSUPPORTED",
            "Dataset does not provide the financial model input protocol",
            "datasetId",
        )
    if "financial_missing" not in attributes or attributes["financial_missing"] not in (0, 1):
        raise DecisionError(
            422,
            "DECISION_INPUT_INVALID",
            "Financial availability must be explicitly provided",
            "financial_missing",
        )
    features: dict = {}
    warnings: list[str] = []
    for name in contract.numeric_features:
        value = attributes.get(name)
        if value is None:
            continue
        if not isinstance(value, (int, float, bool)) or not math.isfinite(value):
            raise DecisionError(422, "DECISION_INPUT_INVALID", "Invalid numeric feature", name)
        # Reproduce the financial training JSON serialization after normalized-table export.
        if name in {"financial_missing", "historical_dormant"}:
            if value not in (0, 1):
                raise DecisionError(422, "DECISION_INPUT_INVALID", "Invalid boolean feature", name)
            features[name] = bool(value)
        else:
            features[name] = int(value) if float(value).is_integer() else value
    for name in contract.categorical_features:
        if attributes.get(name) is not None:
            value = attributes[name]
            if not isinstance(value, str) or not value.strip():
                raise DecisionError(422, "DECISION_INPUT_INVALID", "Invalid category", name)
            features[name] = value
            continue
        prefix = f"cat:{name}:"
        columns = {key: value for key, value in attributes.items() if key.startswith(prefix)}
        if any(value not in (0, 1) for value in columns.values()):
            raise DecisionError(422, "DECISION_INPUT_INVALID", "Invalid category encoding", name)
        active = [key[len(prefix) :] for key, value in columns.items() if value == 1]
        if len(active) > 1:
            raise DecisionError(422, "DECISION_INPUT_INVALID", "Ambiguous category encoding", name)
        if active and active[0] != "__unknown__":
            features[name] = active[0]
        elif active:
            warnings.append(f"Original category unavailable in source encoding: {name}")
    return {"state": {"features": features}}, warnings
