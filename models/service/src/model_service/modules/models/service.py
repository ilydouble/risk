"""Bounded artifact loading and inference, independent of HTTP DTOs."""

import asyncio

from stellarmesh_objectstorage import AsyncClient

from model_service.adapters.archive import unpack
from model_service.execution.process import ComputationFailed, run_cli
from model_service.files import digest, verify
from model_service.modules.jobs.repository import Store
from model_service.shared.config import Settings


class Runtime:
    def __init__(self, store: Store, storage: AsyncClient, settings: Settings):
        self.store, self.storage, self.settings = store, storage, settings
        self.slot = asyncio.Semaphore(1)

    async def predict(self, job_id: str, ids: list[str]) -> list[dict]:
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
                await asyncio.to_thread(unpack, archive, directory)
            await asyncio.to_thread(verify, directory, "riskgnn-model-v1")

            async def ignore(_kind: str, _data: dict) -> None:
                pass

            try:
                async with asyncio.timeout(60):
                    return await run_cli(
                        ["predict", "--input", str(directory), "--ids", *ids], ignore
                    )
            except ComputationFailed as error:
                if "Unknown bound-graph enterprise" in str(error):
                    raise KeyError("Unknown bound-graph enterprise") from error
                raise
