"""Bounded artifact transport and adapter inference, independent of model files."""

import asyncio
import shutil
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient

from model_service.adapters.archive import unpack
from model_service.adapters.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.artifacts import fingerprint
from model_service.execution.invocation import Invocation
from model_service.execution.process import ComputationFailed, run_adapter
from model_service.files import digest
from model_service.modules.jobs.repository import Store
from model_service.shared.config import Settings


class Runtime:
    def __init__(self, store: Store, storage: AsyncClient, settings: Settings):
        self.store, self.storage, self.settings = store, storage, settings
        self.slot = asyncio.Semaphore(1)

    async def predict(self, job_id: str, ids: list[str], request_id: str = "") -> list[dict]:
        if self.slot.locked():
            raise RuntimeError("Inference slot is busy")
        async with self.slot:
            job = await self.store.get(job_id)
            if job["status"] != "completed" or job["kind"] != "train":
                raise ValueError("Model artifact is not ready")
            result = job["result"]
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
            # Old published records predate adapter identity. Keep this mapping at
            # the existing RiskGNN endpoint, not in the generic execution protocol.
            invocation = Invocation(
                adapter_id=result.get(
                    "adapterId", job["payload"].get("runnerId", "riskgnn-node-edge")
                ),
                adapter_version=result.get("adapterVersion", "1.0.0"),
                request=OperationRequest(
                    operation=Operation.PREDICT,
                    inputs={
                        "model": AssetInput(
                            path=directory,
                            sha256=await asyncio.to_thread(fingerprint, directory),
                            format=result.get("format", "riskgnn-model-v1"),
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
                    result_data = (await run_adapter(invocation, ignore)).result.data
                    items = result_data["items"]
                    if not isinstance(items, list) or not all(
                        isinstance(item, dict) for item in items
                    ):
                        raise ValueError("Adapter prediction result has invalid shape")
                    return [dict(item) for item in items if isinstance(item, dict)]
            except ComputationFailed as error:
                if error.detail.code == "RISKGNN_COMPANY_NOT_FOUND":
                    raise KeyError(error.detail.message) from error
                raise
            finally:
                shutil.rmtree(call_directory, ignore_errors=True)
