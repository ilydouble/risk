"""Compatibility for the existing RiskGNN screen; execution itself is adapter-neutral.

This module selects operations and projects their summaries into the existing HTTP
contract. Dataset loading/splitting/training rules remain entirely in the adapter.
"""

import asyncio

from model_service.execution.artifacts import artifact_paths, fingerprint
from model_service.execution.contracts import (
    AssetInput,
    ExecutionError,
    Operation,
    OperationRequest,
)
from model_service.execution.executor import Executor
from model_service.execution.invocation import Invocation
from model_service.execution.runtime import runtime_spec
from model_service.files import digest
from model_service.shared.dataset_contract import read_dataset_contract


async def execute_workflow(job, settings, store, storage) -> dict:
    async def event(kind: str, data: dict):
        await store.event(job["id"], job["owner"], kind, data)

    executor = Executor(storage, event)
    base = settings.workspace / "jobs" / job["id"]
    directory = base / str(job["attempt"])
    directory.mkdir(parents=True, exist_ok=True)
    if job["payload"].get("runnerId", "riskgnn") != "riskgnn":
        raise ExecutionError("MODEL_RUNTIME_INCOMPATIBLE", "Only RiskGNN is deployed")
    runtime_id = "riskgnn"
    version = runtime_spec().runtime_version

    def invocation(operation, inputs, parameters=None, configuration=None):
        return Invocation(
            runtime_id=runtime_id,
            runtime_version=version,
            request=OperationRequest(
                operation=operation,
                inputs=inputs,
                parameters=parameters or {},
                configuration=configuration or {},
            ),
            run_id=job["id"],
            attempt_id=str(job["attempt"]),
            request_id=job["requestId"],
            directory=directory / operation.value,
        )

    async def execute(call):
        previous = [
            base / str(number) / call.request.operation.value
            for number in range(job["attempt"] - 1, 0, -1)
        ]
        return await executor.execute(call, previous)

    archive = directory / "source.zip"
    if job["kind"] == "validate":
        await storage.download_file(job["payload"]["objectKey"], archive)
        sha = await asyncio.to_thread(digest, archive)
        call = invocation(
            Operation.INSPECT, {"dataset": AssetInput(path=archive, sha256=sha, format="zip")}
        )
        result = await execute(call)
        # Analysis-only results can remain visible, but a corrupt upload must not be
        # marked ready merely because inspect successfully returned diagnostics.
        if not result.data.get("protocol"):
            raise ExecutionError("DATASET_INCOMPATIBLE", str(result.data.get("issues", [])))
        key = f"datasets/{job['id']}/{sha}/source.zip"
        await storage.upload_file(key, archive, content_type="application/zip")
        artifacts = await executor.upload(call, result)
        return {
            **result.data,
            "objectKey": key,
            "runtimeId": runtime_id,
            "runtimeVersion": version,
            "enterpriseArtifact": artifacts.get("enterprises"),
        }

    source = await store.get(job["payload"]["sourceJobId"])
    if source["kind"] != "validate" or source["status"] != "completed":
        raise ValueError("Dataset validation is not complete")
    data = source["result"]
    await storage.download_file(data["objectKey"], archive)
    configuration = job["payload"].get("configuration")
    train_call = invocation(
        Operation.TRAIN,
        {"dataset": AssetInput(path=archive, sha256=data["sha256"], format="zip")},
        configuration["resolvedParameters"]
        if configuration
        else {"epochs": job["payload"].get("epochs") or 2},
        configuration,
    )
    await asyncio.to_thread(read_dataset_contract, archive)
    trained = await execute(train_call)
    model = artifact_paths(train_call.directory / "output", trained)["model"]
    model_sha = await asyncio.to_thread(fingerprint, model)
    test_call = invocation(
        Operation.EVALUATE,
        {
            "model": AssetInput(
                path=model, sha256=model_sha, format=trained.artifacts["model"].format
            )
        },
    )
    tested = await execute(test_call)
    await event("stage", {"stage": "uploading", "message": ""})
    artifacts = await executor.upload(train_call, trained)
    artifacts.update(await executor.upload(test_call, tested))
    return {
        **artifacts["model"],
        "report": tested.data["report"],
        "profile": trained.data["profile"],
        "companies": trained.data["companies"],
        "runtimeId": runtime_id,
        "runtimeVersion": version,
        "artifacts": artifacts,
        "effectiveConfig": trained.effective_config,
        "actualCounts": trained.data["profile"].get("actualCounts", {}),
    }
