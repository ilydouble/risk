"""Model-owned CLI: data adapters, training, evaluation and prediction."""

import argparse
import json
import signal
import traceback
from pathlib import Path

import torch
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from riskgnn.dataset_adapters.enterprise import FORMAT, export
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.workbench.artifacts import asset_digest, read_json, write_json
from riskgnn.workbench.configuration import ConfigurationError, merge, validate_frozen
from riskgnn.workbench.configuration import resolve as resolve_configuration
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.training import evaluate, train


class OperationFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def execute(request: dict, directory: Path, emit) -> dict:
    operation = request["operation"]
    inputs, parameters = request["inputs"], request["parameters"]
    work, output = directory / "work", directory / "output"
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    if operation == "configure":
        configuration = resolve_configuration(
            parameters["dataset_contract"],
            parameters.get("requested_parameters", {}),
            parameters.get("expected_digest"),
        )
        return {"data": configuration}
    if operation == "inspect":
        emit({"kind": "stage", "stage": "validating", "message": ""})
        data = inspect(Path(inputs["dataset"]["path"]), work / "validated")
        adapter, _ = resolve(Path(inputs["dataset"]["path"]))
        data["enterpriseData"] = export(
            adapter, work / "validated", output / "enterprises.jsonl", data
        )
        return {
            "data": data,
            "effective_config": parameters,
            "artifacts": {
                "enterprises": {"path": "enterprises.jsonl", "format": FORMAT}
            },
        }
    if operation == "train":
        source = Path(inputs["dataset"]["path"])
        adapter, contract = resolve(source)
        configuration = (
            validate_frozen(contract, parameters, request["configuration"])
            if request.get("configuration")
            else resolve_configuration(contract, parameters)
        )
        parameters = configuration["resolvedParameters"]
        if not adapter.trainable:
            raise OperationFailure(
                "DATASET_ANALYSIS_ONLY",
                "This dataset adapter does not support training",
            )
        emit({"kind": "stage", "stage": "validating", "message": ""})
        inspect(source, work / "validated")
        emit({"kind": "stage", "stage": "preparing", "message": ""})
        adapter.prepare(work / "validated", work / "prepared", parameters["dataset"])
        emit({"kind": "stage", "stage": "training", "message": ""})

        def metric(row):
            for name, group in (
                ("trainLoss", "train"),
                ("validationLoss", "validation"),
            ):
                emit(
                    {
                        "kind": "metric",
                        "name": "loss",
                        "value": row[name],
                        "step": row["epoch"],
                        "group": group,
                    }
                )

        profile = train(
            work / "prepared",
            output / "model",
            parameters["epochs"],
            metric_callback=metric,
            configuration=configuration,
        )
        return {
            "data": {
                "profile": profile,
                "companies": read_json(output / "model/ids.json")[
                    : min(100, profile.get("companyCount", profile["nodeCount"]))
                ],
            },
            "artifacts": {"model": {"path": "model", "format": "riskgnn-model-v2"}},
            "effective_config": parameters,
        }
    if operation == "evaluate":
        emit({"kind": "stage", "stage": "testing", "message": ""})
        report = evaluate(Path(inputs["model"]["path"]), output=output / "report")
        report["modelSha256"] = inputs["model"]["sha256"]
        write_json(output / "report/metrics.json", report)
        return {
            "data": {"report": report},
            "artifacts": {
                "report": {"path": "report", "format": "riskgnn-evaluation-v2"}
            },
        }
    if operation == "predict":
        emit({"kind": "stage", "stage": "predicting", "message": ""})
        try:
            items = Predictor(Path(inputs["model"]["path"])).predict(
                parameters["company_ids"]
            )
        except KeyError as error:
            raise OperationFailure("RISKGNN_COMPANY_NOT_FOUND", str(error)) from error
        return {"data": {"items": items}, "effective_config": parameters}
    raise OperationFailure("MODEL_OPERATION_UNSUPPORTED", operation)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    command = read_json(args.request)
    directory = Path(command["directory"])
    directory.mkdir(parents=True, exist_ok=True)
    cancelled = False

    def cancel(_signum, _frame):
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, cancel)
    torch.set_num_threads(command.get("resources", {}).get("threads", 2))
    with (directory / "events.jsonl").open("w") as stream:

        def emit(event):
            if cancelled:
                raise OperationFailure("EXECUTION_CANCELLED", "Operation cancelled")
            stream.write(json.dumps(event, allow_nan=False) + "\n")
            stream.flush()

        try:
            if (
                command.get("contract_version") != 2
                or command.get("runtime_id") != "riskgnn"
                or command.get("runtime_version") != "2"
            ):
                raise OperationFailure(
                    "MODEL_RUNTIME_INCOMPATIBLE", "Unsupported execution contract"
                )
            for asset in command["request"]["inputs"].values():
                if asset_digest(Path(asset["path"])) != asset["sha256"]:
                    raise OperationFailure(
                        "MODEL_INPUT_INVALID", "Input asset checksum mismatch"
                    )
            descriptor = read_json(Path(__file__).with_name("runtime.json"))
            operation = descriptor["operations"][command["request"]["operation"]]
            if not command["request"].get("configuration"):
                command["request"]["parameters"] = merge(
                    operation["default_parameters"],
                    command["request"].get("parameters", {}),
                )
            Draft202012Validator(operation["parameters_schema"]).validate(
                command["request"]["parameters"]
            )
            result = execute(command["request"], directory, emit)
            Draft202012Validator(operation["result_schema"]).validate(result["data"])
            if cancelled:
                raise OperationFailure("EXECUTION_CANCELLED", "Operation cancelled")
            write_json(directory / "operation-result.json", result)
        except Exception as error:
            if isinstance(error, OperationFailure):
                code = error.code
            elif isinstance(error, ConfigurationError):
                code = (
                    "MODELING_CONFIG_STALE"
                    if error.stale
                    else "EXECUTION_PARAMETERS_INVALID"
                )
            elif isinstance(
                error, (ValueError, KeyError, FileNotFoundError, SchemaValidationError)
            ):
                code = "MODEL_INPUT_INVALID"
            else:
                code = "MODEL_EXECUTION_FAILED"
            write_json(
                directory / "error.json",
                {"code": code, "message": str(error), "retryable": False},
            )
            traceback.print_exc()
            raise SystemExit(1) from error


if __name__ == "__main__":
    main()
