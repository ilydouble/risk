"""One CLI invocation, independent of model/data implementation."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from model_service.execution.artifacts import artifact_paths, fingerprint, inventory
from model_service.execution.contracts import (
    Contract,
    ExecutionError,
    OperationRequest,
    OperationResult,
    RuntimeSpec,
    validate_request,
    validate_result,
)
from model_service.files import read_json, write_json


class Invocation(Contract):
    contract_version: Literal[2] = 2
    runtime_id: str
    runtime_version: str
    request: OperationRequest
    run_id: str
    attempt_id: str
    request_id: str
    directory: Path
    device: Literal["cpu"] = "cpu"
    resources: dict[str, int] = Field(default_factory=lambda: {"threads": 2})

    @field_validator("directory")
    @classmethod
    def absolute_directory(cls, value: Path) -> Path:
        return value.absolute()

    def binding(self) -> str:
        # Paths/attempt IDs change on retry. Content, exact adapter version and
        # parameters must remain identical before sealed output can be reused.
        value = self.model_dump(mode="json", exclude={"directory", "attempt_id", "request_id"})
        for asset in value["request"]["inputs"].values():
            asset.pop("path")
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Receipt(Contract):
    binding: str
    result: OperationResult
    files: dict[str, dict]


def verify_receipt(invocation: Invocation) -> Receipt:
    receipt = Receipt.model_validate(read_json(invocation.directory / "result.json"))
    if receipt.binding != invocation.binding():
        raise ExecutionError("EXECUTION_RESULT_INVALID", "Result does not match invocation")
    actual = {
        role: inventory(path)
        for role, path in artifact_paths(invocation.directory / "output", receipt.result).items()
    }
    if actual != receipt.files:
        raise ExecutionError("EXECUTION_ARTIFACT_INVALID", "Sealed artifact checksum mismatch")
    return receipt


def validate_inputs(invocation: Invocation, spec: RuntimeSpec) -> None:
    if (spec.runtime_id, spec.runtime_version) != (
        invocation.runtime_id,
        invocation.runtime_version,
    ):
        raise ExecutionError("MODEL_RUNTIME_INCOMPATIBLE", "Model runtime/version mismatch")
    validate_request(spec, invocation.request)
    for asset in invocation.request.inputs.values():
        if fingerprint(asset.path) != asset.sha256:
            raise ExecutionError("EXECUTION_INPUT_INVALID", "Input checksum mismatch")


def finalize(invocation: Invocation, spec: RuntimeSpec, result: OperationResult) -> Receipt:
    # The model CLI writes only operation-result.json; the service independently
    # validates it and seals the trusted completion receipt.
    validate_inputs(invocation, spec)
    validate_result(spec, invocation.request, result)
    paths = artifact_paths(invocation.directory / "output", result)
    for role, path in paths.items():
        expected = spec.operations[invocation.request.operation].artifacts[role].kind
        if (expected == "file" and not path.is_file()) or (
            expected == "directory" and not path.is_dir()
        ):
            raise ExecutionError("EXECUTION_ARTIFACT_INVALID", f"Wrong artifact kind: {role}")
    if len(result.model_dump_json()) > 1024 * 1024:
        raise ExecutionError(
            "EXECUTION_RESULT_INVALID", "Large results must be returned as artifacts"
        )
    receipt = Receipt(
        binding=invocation.binding(),
        result=result,
        files={role: inventory(path) for role, path in paths.items()},
    )
    write_json(invocation.directory / "result.json", receipt.model_dump(mode="json"))
    return receipt
