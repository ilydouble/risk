import argparse
import asyncio
import logging
import signal

from sqlalchemy import text
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from model_service.adapters.contracts import AdapterError
from model_service.modules.jobs.operations import execute_operation
from model_service.modules.jobs.repository import LostLease, Store
from model_service.modules.jobs.workflows import execute_workflow
from model_service.shared.config import Settings
from model_service.shared.db import create_engine
from model_service.shared.logging import configure_logging

logger = logging.getLogger("riskgnn.worker")


class Worker:
    def __init__(self, settings: Settings, store: Store, storage: AsyncClient):
        self.settings, self.store, self.storage = settings, store, storage

    async def execute(self, job: dict) -> dict:
        if job["kind"] == "execute":
            return await execute_operation(job, self.settings, self.store, self.storage)
        return await execute_workflow(job, self.settings, self.store, self.storage)

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
        except (AdapterError, ValueError) as error:
            message = str(error)
            if isinstance(error, AdapterError):
                try:
                    await self.store.event(
                        job["id"],
                        job["owner"],
                        "log",
                        {
                            "level": "error",
                            "message": message,
                            "error": error.detail.model_dump(mode="json"),
                        },
                    )
                except LostLease:
                    pass  # finish below is fenced and can only close this owner's attempt.
            retryable = isinstance(error, AdapterError) and error.detail.retryable
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
    engine = create_engine(settings)
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
