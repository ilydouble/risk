"""Bounded artifact transport and adapter inference, independent of model files."""

import asyncio
import shutil
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient

from model_service.execution.artifacts import fingerprint
from model_service.execution.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.invocation import Invocation
from model_service.execution.process import ComputationFailed, run_model
from model_service.execution.runtime import runtime_spec
from model_service.files import digest
from model_service.modules.jobs.repository import Store
from model_service.shared.archive import unpack
from model_service.shared.config import Settings


class Runtime:
    def __init__(self, store: Store, storage: AsyncClient, settings: Settings):
        self.store, self.storage, self.settings = store, storage, settings
        self.slot = asyncio.Semaphore(1)
        self.configuration_slot = asyncio.Semaphore(1)

    async def configuration(
        self,
        job_id: str,
        parameters: dict,
        expected_digest: str | None,
        request_id: str,
    ) -> dict:
        job = await self.store.get(job_id)
        if job["kind"] != "validate" or job["status"] != "completed":
            raise ValueError("Dataset validation is not complete")
        # Reuse the immutable contract from inspection; do not scan the dataset for a form.
        if self.configuration_slot.locked():
            raise RuntimeError("Configuration slot is busy")
        async with self.configuration_slot:
            directory = self.settings.workspace / "configuration" / uuid4().hex
            invocation = Invocation(
                runtime_id="riskgnn",
                runtime_version=runtime_spec().runtime_version,
                request=OperationRequest(
                    operation=Operation.CONFIGURE,
                    parameters={
                        "dataset_contract": job["result"]["datasetContract"],
                        "requested_parameters": parameters,
                        "expected_digest": expected_digest,
                    },
                ),
                run_id=job_id,
                attempt_id=uuid4().hex,
                request_id=request_id,
                directory=directory,
            )

            async def ignore(_kind: str, _data: dict) -> None:
                pass

            try:
                async with asyncio.timeout(60):
                    return dict((await run_model(invocation, ignore)).result.data)
            finally:
                shutil.rmtree(directory, ignore_errors=True)

    async def predict(self, job_id: str, ids: list[str], request_id: str = "") -> list[dict]:
        if self.slot.locked():
            raise RuntimeError("Inference slot is busy")
        async with self.slot:
            job = await self.store.get(job_id)
            if job["status"] != "completed" or job["kind"] != "train":
                raise ValueError("Model artifact is not ready")
            result = job["result"]
            if result.get("runtimeId") != "riskgnn" or result.get("runtimeVersion") not in {
                "2",
                "3",
            }:
                raise ValueError("Model belongs to a retired workbench protocol")
            directory = self.settings.workspace / "models" / result["sha256"]
            if not directory.exists():
                archive = directory.with_suffix(".zip")
                archive.parent.mkdir(parents=True, exist_ok=True)
                await self.storage.download_file(result["objectKey"], archive)
                if await asyncio.to_thread(digest, archive) != result["sha256"]:
                    raise ValueError("Model download checksum mismatch")
                temporary = directory.with_name(directory.name + ".partial")
                shutil.rmtree(temporary, ignore_errors=True)
                await asyncio.to_thread(unpack, archive, temporary)
                temporary.rename(directory)
            call_directory = self.settings.workspace / "inference" / uuid4().hex
            invocation = Invocation(
                runtime_id="riskgnn",
                runtime_version=runtime_spec().runtime_version,
                request=OperationRequest(
                    operation=Operation.PREDICT,
                    inputs={
                        "model": AssetInput(
                            path=directory,
                            sha256=await asyncio.to_thread(fingerprint, directory),
                            format=result.get("format", "riskgnn-model-v2"),
                        )
                    },
                    parameters={"company_ids": [item for item in ids]},
                ),
                run_id=job_id,
                attempt_id=uuid4().hex,
                request_id=request_id or job["requestId"],
                directory=call_directory,
            )

            async def ignore(_kind: str, _data: dict) -> None:
                pass

            try:
                async with asyncio.timeout(60):
                    result_data = (await run_model(invocation, ignore)).result.data
                    items = result_data["items"]
                    if not isinstance(items, list) or not all(
                        isinstance(item, dict) for item in items
                    ):
                        raise ValueError("Model prediction result has invalid shape")
                    return [dict(item) for item in items if isinstance(item, dict)]
            except ComputationFailed as error:
                if error.detail.code == "RISKGNN_COMPANY_NOT_FOUND":
                    raise KeyError(error.detail.message) from error
                raise
            finally:
                shutil.rmtree(call_directory, ignore_errors=True)
