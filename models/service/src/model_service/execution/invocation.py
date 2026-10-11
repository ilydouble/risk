"""One CLI invocation, independent of model/data implementation."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from model_service.adapters.contracts import (
    AdapterError,
    Contract,
    ExecutionContext,
    ModelAdapter,
    OperationRequest,
    OperationResult,
    parameters_for,
    validate_request,
    validate_result,
)
from model_service.execution.artifacts import artifact_paths, fingerprint, inventory
from model_service.files import read_json, write_json


class Invocation(Contract):
    contract_version: Literal[1] = 1
    adapter_id: str
    adapter_version: str
    request: OperationRequest
    run_id: str
    attempt_id: str
    request_id: str
    directory: Path
    device: Literal["cpu"] = "cpu"
    resources: dict[str, int] = Field(default_factory=lambda: {"threads": 2})

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
        raise AdapterError("ADAPTER_RESULT_INVALID", "Result does not match invocation")
    actual = {
        role: inventory(path)
        for role, path in artifact_paths(invocation.directory / "output", receipt.result).items()
    }
    if actual != receipt.files:
        raise AdapterError("ADAPTER_ARTIFACT_INVALID", "Sealed artifact checksum mismatch")
    return receipt


def invoke(adapter: ModelAdapter, invocation: Invocation, context: ExecutionContext) -> Receipt:
    spec = adapter.describe()
    if (spec.adapter_id, spec.adapter_version) != (
        invocation.adapter_id,
        invocation.adapter_version,
    ):
        raise AdapterError("ADAPTER_NOT_AVAILABLE", "Adapter identity/version mismatch")
    request = invocation.request.model_copy(
        update={
            "parameters": parameters_for(
                spec, invocation.request.operation, invocation.request.parameters
            )
        }
    )
    validate_request(spec, request)
    for asset in request.inputs.values():
        if fingerprint(asset.path) != asset.sha256:
            raise AdapterError("ADAPTER_INPUT_INVALID", "Input checksum mismatch")
    context.work_dir.mkdir(parents=True, exist_ok=True)
    context.output_dir.mkdir(parents=True, exist_ok=True)
    context.check_cancelled()
    result = adapter.execute(request, context)
    context.check_cancelled()
    if not isinstance(result, OperationResult):
        raise AdapterError("ADAPTER_RESULT_INVALID", "Adapter must return OperationResult")
    # Validation is repeated after execution; adapters cannot silently mutate inputs.
    for asset in request.inputs.values():
        if fingerprint(asset.path) != asset.sha256:
            raise AdapterError("ADAPTER_INPUT_MUTATED", "Adapter modified an input asset")
    validate_result(spec, request, result)
    paths = artifact_paths(context.output_dir, result)
    for role, path in paths.items():
        expected = spec.operations[request.operation].artifacts[role].kind
        if (expected == "file" and not path.is_file()) or (
            expected == "directory" and not path.is_dir()
        ):
            raise AdapterError("ADAPTER_ARTIFACT_INVALID", f"Wrong artifact kind: {role}")
    if len(result.model_dump_json()) > 1024 * 1024:
        raise AdapterError("ADAPTER_RESULT_INVALID", "Large results must be returned as artifacts")
    receipt = Receipt(
        binding=invocation.binding(),
        result=result,
        files={role: inventory(path) for role, path in paths.items()},
    )
    write_json(invocation.directory / "result.json", receipt.model_dump(mode="json"))
    return receipt
