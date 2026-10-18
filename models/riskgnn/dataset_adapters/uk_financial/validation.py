"""Scan every financial row and bind identities, labels and bytes before publishing records."""

import json
import math
from pathlib import Path

from jsonschema.exceptions import ValidationError

from riskgnn.dataset_adapters.archive import unpack
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult
from riskgnn.dataset_adapters.delivery import delivery_for
from riskgnn.dataset_adapters.uk_financial.readers import (
    FILES,
    document_validator,
    input_contract,
    json_rows,
    observation_index,
)
from riskgnn.workbench.artifacts import digest

PROTOCOL = "uk-financial-jsonl-v1"
NORMALIZED = "financial-observations.jsonl"


def validate(source: Path, workspace: Path, config: dict) -> InspectionResult:
    delivery = delivery_for("uk-financial-jsonl", "1")
    delivery.config(config)
    _, relative = read_contract(source)
    files = unpack(source, workspace / "source")
    root = workspace / "source" / relative
    delivery.check_files(root)
    manifest = json.loads((root / "manifest.json").read_text())
    contract = input_contract()
    if manifest.get("format") != "uk-labelled-decisions-v1" or (
        manifest.get("target") != contract["question"]["instructions"]
    ):
        raise ValueError("Unsupported financial source manifest/target")
    # The supplied manifest also describes graph files. This adapter consumes only the five
    # declared financial inputs, and explicitly excludes those optional graph artifacts.
    for name in (*FILES.values(), "sample-index.jsonl"):
        record = manifest.get("files", {}).get(name, {})
        path = root / name
        if record.get("bytes") != path.stat().st_size or record.get("sha256") != digest(path):
            raise ValueError("Financial source file size/checksum mismatch: " + name)
    index = observation_index(root / "sample-index.jsonl")
    manifest_sha256 = digest(root / "manifest.json")
    validator = document_validator(contract)
    names = contract["numeric_features"] + contract["categorical_features"]
    splits, total, positives = [], 0, 0
    temporary = workspace / (NORMALIZED + ".partial")
    try:
        with temporary.open("w", encoding="utf-8") as output:
            for split, filename in FILES.items():
                count, positive, companies = 0, 0, set()
                for number, document in json_rows(root / filename):
                    try:
                        validator.validate(document)
                    except ValidationError as error:
                        field = ".".join(map(str, error.path)) or "document"
                        raise ValueError(f"Invalid financial input field: {field}") from None
                    properties = index.pop((split, number), None)
                    if properties is None:
                        raise ValueError("Missing financial sample-index position")
                    features = document["state"]["features"]
                    if features["financial_missing"] not in (False, True):
                        raise ValueError("Invalid financial_missing flag")
                    if any(
                        isinstance(value, (int, float)) and not math.isfinite(value)
                        for value in features.values()
                    ):
                        raise ValueError("Non-finite financial value")
                    label = int(document["expected"][contract["question_id"]] == "event")
                    record = EnterpriseRecord(
                        kind="company",
                        snapshot=split,
                        nodeId=properties["sample_id"],
                        data={
                            "name": properties["company_id"],
                            "properties": properties,
                            "attributes": {name: features.get(name) for name in names},
                            "label": label,
                            "split": split,
                            "sourceRecord": {
                                "file": filename,
                                "line": number,
                                "manifestSha256": manifest_sha256,
                            },
                        },
                    )
                    output.write(record.model_dump_json() + "\n")
                    count += 1
                    positive += label
                    companies.add(properties["company_id"])
                declared = manifest["splits"][split]
                if (
                    count != declared["samples"]
                    or positive != declared["labels"]["1"]
                    or count - positive != declared["labels"]["0"]
                    or len(companies) != declared["companies"]
                ):
                    raise ValueError("Financial split counts do not match source manifest")
                splits.append({"split": split, "count": count, "positives": positive})
                total += count
                positives += positive
        if index:
            raise ValueError("Unreferenced financial sample-index rows")
        temporary.replace(workspace / NORMALIZED)
    finally:
        temporary.unlink(missing_ok=True)
    return InspectionResult.model_validate(
        {
            "protocol": PROTOCOL,
            "sha256": digest(source),
            "root": "source/" + relative if relative != "." else "source",
            "files": files,
            "counts": {
                "company_attr": total,
                "edges": 0,
                "hyperedges": 0,
                "events": 0,
                "persons": 0,
            },
            "features": names,
            "labeledCount": total,
            "positiveCount": positives,
            "splits": splits,
            "datasetProfile": {
                "datasetFormat": PROTOCOL,
                "taskType": "financial_observation",
                "target": contract["question"]["instructions"],
                "evaluation": "provided_frozen_splits",
                "metadata": {
                    "inputContractVersion": contract["contract_version"],
                    "countMeaning": "dated company observations, not distinct companies",
                },
            },
            "limitations": [
                "Inference/browsing only; does not train RiskGNN.",
                "Matched research cohort, not population default risk.",
                "Financial source contains no graph relations.",
                "Training split includes the source calibration selection pool.",
            ],
        }
    )
