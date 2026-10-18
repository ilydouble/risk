"""Bounded source reads and the frozen financial input specification."""

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

MODEL_VERSION = "uk-financial-0.6b-v1"
FILES = {split: f"{split}.financial.jsonl" for split in ("train", "valid", "test")}
MAX_ROWS = 500000
MAX_LINE = 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_number(_value):
    raise ValueError("Non-finite JSON number")


def json_rows(path: Path):
    with path.open(encoding="utf-8") as stream:
        for number in range(1, MAX_ROWS + 2):
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            if number > MAX_ROWS or len(line.encode()) > MAX_LINE:
                raise ValueError("Financial source exceeds row/line limits")
            value = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_number)
            if not isinstance(value, dict):
                raise TypeError("Financial source rows must be objects")
            yield number, value


def input_contract() -> dict:
    root = Path(__file__).resolve().parents[3]
    return json.loads(
        (root / "uk_decision/releases" / MODEL_VERSION / "input-contract.json").read_text()
    )


def document_validator(contract: dict) -> Draft202012Validator:
    properties = {name: {"type": ["number", "boolean"]} for name in contract["numeric_features"]}
    properties.update(
        {
            name: {"type": "string", "minLength": 1, "maxLength": 512}
            for name in contract["categorical_features"]
        }
    )
    question_id = contract["question_id"]
    return Draft202012Validator(
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["state", "questions", "expected"],
            "properties": {
                "state": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["features"],
                    "properties": {
                        "features": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["financial_missing"],
                            "properties": properties,
                        }
                    },
                },
                "questions": {"const": {question_id: contract["question"]}},
                "expected": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [question_id],
                    "properties": {question_id: {"enum": ["no_event", "event"]}},
                },
            },
        }
    )


def observation_index(path: Path) -> dict:
    result, identities = {}, set()
    for _, row in json_rows(path):
        split, line = row.get("split"), row.get("line")
        if split not in FILES or type(line) is not int or not 1 <= line <= MAX_ROWS:
            raise ValueError("Invalid financial index split/line")
        sample, company = row.get("sample_id"), row.get("company_id")
        if any(
            not isinstance(value, str) or not 0 < len(value) <= 512 for value in (sample, company)
        ):
            raise ValueError("Invalid financial observation/company ID")
        month, end = row.get("observation_month", ""), row.get("followup_end_month", "")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month) or (
            end != f"{int(month[:4]) + 1:04d}{month[4:]}"
            or row.get("prediction_horizon_months") != 12
        ):
            raise ValueError("Invalid observation month or prediction horizon")
        if sample in identities or (split, line) in result:
            raise ValueError("Duplicate financial observation or index position")
        identities.add(sample)
        result[(split, line)] = row
    return result
