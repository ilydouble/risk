import argparse
import asyncio
import logging
import shutil
import signal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from service.config import Settings, configure_logging
from service.execution.process import ComputationFailed, run_cli
from service.execution.store import LostLease, Store
from service.files import digest, export_zip, read_json, verify, write_json
from service.runners.registry import DEFAULT_MODEL, require_model

logger = logging.getLogger("riskgnn.worker")


class Worker:
    def __init__(self, settings: Settings, store: Store, storage: AsyncClient):
        self.settings, self.store, self.storage = settings, store, storage

    async def phase(self, job: dict, name: str, args: list[str]):
        async def event(kind: str, data: dict):
            await self.store.event(job["id"], job["owner"], kind, data)

        await event("state", {"stage": name})
        return await run_cli(args, event)

    async def execute(self, job: dict) -> dict:
        base = self.settings.workspace / "jobs" / job["id"]
        directory = base / str(job["attempt"])
        directory.mkdir(parents=True, exist_ok=True)
        if job["kind"] == "validate":
            archive = directory / "source.zip"
            await self.storage.download_file(job["payload"]["objectKey"], archive)
            result = await self.phase(
                job,
                "validating",
                [
                    "validate-data",
                    "--input",
                    str(archive),
                    "--output",
                    str(directory / "validated"),
                ],
            )
            key = f"datasets/{job['id']}/{result['sha256']}/source.zip"
            await self.storage.upload_file(key, archive, content_type="application/zip")
            result["objectKey"] = key
            return result

        source = await self.store.get(job["payload"]["sourceJobId"])
        if source["kind"] != "validate" or source["status"] != "completed":
            raise ValueError("Dataset validation is not complete")
        source_result = source["result"]
        runner_id = job["payload"].get("runnerId") or DEFAULT_MODEL
        require_model(runner_id, source_result["protocol"])
        model = directory / "model"
        # A sealed checkpoint in a prior attempt can resume only this immutable job.
        # Copy it into the new attempt so a stale worker cannot overwrite this output.
        for number in range(job["attempt"] - 1, 0, -1):
            previous = base / str(number) / "model"
            try:
                manifest = await asyncio.to_thread(verify, previous, "riskgnn-model-v1")
                if manifest["sourceSha256"] == source_result["sha256"]:
                    await asyncio.to_thread(shutil.copytree, previous, model, dirs_exist_ok=True)
                    await asyncio.to_thread(verify, model, "riskgnn-model-v1")
                    await self.store.event(
                        job["id"],
                        job["owner"],
                        "log",
                        {"message": "Resumed sealed training result"},
                    )
                    break
            except (OSError, ValueError, KeyError):
                continue
        if not (model / "manifest.json").exists():
            cached = self.settings.workspace / "datasets" / source_result["sha256"]
            if not (cached / "validation.json").exists():
                archive = directory / "source.zip"
                await self.storage.download_file(source_result["objectKey"], archive)
                if await asyncio.to_thread(digest, archive) != source_result["sha256"]:
                    raise ValueError("Dataset checksum mismatch")
                await self.phase(
                    job,
                    "validating",
                    ["validate-data", "--input", str(archive), "--output", str(cached)],
                )
            prepared = directory / "prepared"
            await self.phase(
                job, "preparing", ["prepare", "--input", str(cached), "--output", str(prepared)]
            )
            await self.phase(
                job,
                "training",
                [
                    "train",
                    "--input",
                    str(prepared),
                    "--output",
                    str(model),
                    "--runner-id",
                    runner_id,
                    "--epochs",
                    str(job["payload"].get("epochs", 2)),
                ],
            )
        if not (model / "metrics.json").exists():
            await self.phase(job, "testing", ["test", "--input", str(model)])
        report, metadata = read_json(model / "metrics.json"), read_json(model / "metadata.json")
        await self.store.event(job["id"], job["owner"], "state", {"stage": "uploading"})
        archive = directory / "model.zip"
        await asyncio.to_thread(export_zip, model, archive)
        sha = await asyncio.to_thread(digest, archive)
        key = f"artifacts/{job['id']}/{job['attempt']}/{sha}.zip"
        await self.storage.upload_file(key, archive, content_type="application/zip")
        result = {
            "objectKey": key,
            "sha256": sha,
            "size": archive.stat().st_size,
            "report": report,
            "profile": metadata,
            "companies": read_json(model / "ids.json")[:100],
        }
        write_json(directory / "uploaded.json", result)
        return result

    async def run_job(self, job: dict) -> None:
        logger.info(
            "job.started",
            extra={"job_id": job["id"], "attempt": job["attempt"], "request_id": job["requestId"]},
        )
        task = asyncio.create_task(self.execute(job))
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=10)
                if not done and not await self.store.heartbeat(job["id"], job["owner"]):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    await self.store.finish(job["id"], job["owner"], error="Execution cancelled")
                    return
            result = await task
            await self.store.finish(job["id"], job["owner"], result=result)
        except LostLease:
            # A cancellation can be noticed by an epoch event before the heartbeat.
            # finish is fenced: it closes that cancellation, but cannot touch a new owner.
            await self.store.finish(job["id"], job["owner"], error="Execution interrupted")
            logger.warning("job.lease_lost", extra={"job_id": job["id"]})
        except (ComputationFailed, ValueError) as error:
            message = str(error)
            retryable = isinstance(error, ComputationFailed) and error.retryable
            await self.store.finish(job["id"], job["owner"], error=message, retryable=retryable)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("job.failed", extra={"job_id": job["id"]})
            await self.store.finish(
                job["id"], job["owner"], error=type(error).__name__, retryable=True
            )
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def run(once: bool = False) -> None:
    settings = Settings()
    configure_logging(settings)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with AsyncClient(
            ClientConfig(
                bucket=settings.bucket,
                region="us-east-1",
                endpoint=settings.endpoint,
                use_path_style=True,
            )
        ) as storage:
            worker = Worker(settings, Store(engine), storage)
            while True:
                # One compute slot across worker restarts/replicas. The connection owns
                # the advisory lock; execution updates still require the attempt lease.
                async with engine.connect() as slot:
                    acquired = await slot.scalar(text("SELECT pg_try_advisory_lock(7264751)"))
                    if acquired:
                        try:
                            job = await worker.store.claim()
                            if job:
                                await worker.run_job(job)
                        finally:
                            await slot.execute(text("SELECT pg_advisory_unlock(7264751)"))
                if once:
                    break
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    once = parser.parse_args().once

    async def supervised():
        task = asyncio.create_task(run(once))
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        try:
            await task
        except asyncio.CancelledError:
            pass  # run_job stops the complete process group; lease expiry enables retry.
        finally:
            loop.remove_signal_handler(signal.SIGTERM)

    asyncio.run(supervised())


if __name__ == "__main__":
    main()
