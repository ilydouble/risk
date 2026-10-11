"""Generic internal operation submission alongside the existing screen's workflow."""

import asyncio
from pathlib import Path

from pydantic import Field

from model_service.execution.artifacts import fingerprint
from model_service.execution.contracts import (
    AssetInput,
    Contract,
    ExecutionError,
    JsonObject,
    Operation,
    OperationRequest,
    parameters_for,
)
from model_service.execution.executor import Executor
from model_service.execution.invocation import Invocation
from model_service.execution.runtime import runtime_spec
from model_service.files import digest
from model_service.shared.archive import unpack


class ObjectInput(Contract):
    object_key: str = Field(pattern=r"^(uploads|datasets|artifacts)/[a-zA-Z0-9_./-]+$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: str


class ExecuteInput(Contract):
    runtime_id: str
    runtime_version: str
    operation: Operation
    inputs: dict[str, ObjectInput]
    parameters: JsonObject = Field(default_factory=dict)


def validate_submission(payload: ExecuteInput) -> None:
    spec = runtime_spec()
    if (payload.runtime_id, payload.runtime_version) != (spec.runtime_id, spec.runtime_version):
        raise ExecutionError("MODEL_RUNTIME_INCOMPATIBLE", "Unsupported model runtime/version")
    parameters_for(spec, payload.operation, payload.parameters)
    inputs = spec.operations[payload.operation].inputs
    if set(payload.inputs) - set(inputs):
        raise ExecutionError("EXECUTION_INPUT_INVALID", "Unknown input role")
    for role, definition in inputs.items():
        asset = payload.inputs.get(role)
        if asset is None:
            if definition.required:
                raise ExecutionError("EXECUTION_INPUT_INVALID", f"Missing input: {role}")
        elif definition.formats and asset.format not in definition.formats:
            raise ExecutionError(
                "EXECUTION_INPUT_INCOMPATIBLE", f"Unsupported input format: {role}"
            )


async def execute_operation(job, settings, store, storage) -> dict:
    payload = ExecuteInput.model_validate(job["payload"])
    validate_submission(payload)
    spec = runtime_spec()
    if (payload.runtime_id, payload.runtime_version) != (spec.runtime_id, spec.runtime_version):
        raise ExecutionError("MODEL_RUNTIME_INCOMPATIBLE", "Unsupported model runtime/version")
    base = settings.workspace / "jobs" / job["id"]
    directory = base / str(job["attempt"])
    directory.mkdir(parents=True, exist_ok=True)
    assets = {}
    for index, (role, reference) in enumerate(payload.inputs.items()):
        # Role names are descriptive, never used as filesystem paths.
        path = directory / f"input-{index}"
        await storage.download_file(reference.object_key, path)
        if await asyncio.to_thread(digest, path) != reference.sha256:
            raise ExecutionError("EXECUTION_INPUT_INVALID", "Downloaded input checksum mismatch")
        if spec.operations[payload.operation].inputs[role].kind == "directory":
            extracted = path.with_suffix(".dir")
            await asyncio.to_thread(unpack, path, extracted)
            path = extracted
        assets[role] = AssetInput(
            path=path, sha256=await asyncio.to_thread(fingerprint, path), format=reference.format
        )
    invocation = Invocation(
        runtime_id=payload.runtime_id,
        runtime_version=payload.runtime_version,
        request=OperationRequest(
            operation=payload.operation, inputs=assets, parameters=payload.parameters
        ),
        run_id=job["id"],
        attempt_id=str(job["attempt"]),
        request_id=job["requestId"],
        directory=directory / "operation",
    )

    async def event(kind: str, data: dict):
        await store.event(job["id"], job["owner"], kind, data)

    executor = Executor(storage, event)
    previous: list[Path] = [base / str(n) / "operation" for n in range(job["attempt"] - 1, 0, -1)]
    result = await executor.execute(invocation, previous)
    artifacts = await executor.upload(invocation, result)
    return {
        "runtimeId": payload.runtime_id,
        "runtimeVersion": payload.runtime_version,
        "operation": payload.operation.value,
        "data": result.data,
        "effectiveConfig": result.effective_config,
        "artifacts": artifacts,
    }
