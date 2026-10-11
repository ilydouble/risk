import asyncio
import shutil
from pathlib import Path

from model_service.adapters.contracts import AdapterError, OperationResult
from model_service.execution.artifacts import artifact_paths, digest, pack
from model_service.execution.invocation import Invocation, verify_receipt
from model_service.execution.process import run_adapter


class Executor:
    """Process/retry/artifact mechanics; never opens model-specific files."""

    def __init__(self, storage, event):
        self.storage, self.event = storage, event

    async def execute(self, invocation: Invocation, previous: list[Path]) -> OperationResult:
        for directory in previous:
            try:
                old = invocation.model_copy(update={"directory": directory})
                await asyncio.to_thread(verify_receipt, old)
            except (OSError, ValueError, AdapterError):
                continue
            # Copy a verified receipt into the new attempt; stale owners only write
            # their own directories and cannot overwrite a later attempt's output.
            invocation.directory.mkdir(parents=True, exist_ok=True)
            if (directory / "output").exists():
                await asyncio.to_thread(
                    shutil.copytree,
                    directory / "output",
                    invocation.directory / "output",
                    dirs_exist_ok=True,
                )
            shutil.copy2(directory / "result.json", invocation.directory / "result.json")
            receipt = await asyncio.to_thread(verify_receipt, invocation)
            await self.event("log", {"level": "info", "message": "Resumed sealed operation result"})
            return receipt.result
        return (await run_adapter(invocation, self.event)).result

    async def upload(self, invocation: Invocation, result: OperationResult) -> dict:
        uploaded = {}
        # Recheck bytes before upload, including resumed operation output.
        await asyncio.to_thread(verify_receipt, invocation)
        for index, (role, path) in enumerate(
            artifact_paths(invocation.directory / "output", result).items()
        ):
            archive = path
            media_type = "application/octet-stream"
            if path.is_dir():
                archive = invocation.directory / f"artifact-{index}.zip"
                await asyncio.to_thread(pack, path, archive)
                media_type = "application/zip"
            sha = await asyncio.to_thread(digest, archive)
            key = f"artifacts/{invocation.run_id}/{invocation.attempt_id}/{index}/{sha}"
            await self.storage.upload_file(key, archive, content_type=media_type)
            uploaded[role] = {
                "objectKey": key,
                "sha256": sha,
                "size": archive.stat().st_size,
                "format": result.artifacts[role].format,
                "kind": "directory" if path.is_dir() else "file",
            }
        return uploaded
