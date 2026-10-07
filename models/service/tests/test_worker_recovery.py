import asyncio
import os
import shutil
from uuid import uuid4

import pytest
from service.adapters.singapore import validate
from service.config import Settings
from service.execution.model import Base
from service.execution.store import Store
from service.execution.worker import Worker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def test_artifact_upload_retry_reuses_independently_tested_checkpoint(export_zip, tmp_path):
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for worker recovery acceptance")

    class Storage:
        failures = 1

        async def download_file(self, _key, target):
            shutil.copy2(export_zip, target)

        async def upload_file(self, key, source, **_kwargs):
            if self.failures:
                self.failures -= 1
                raise OSError("transient upload failure")
            shutil.copy2(source, tmp_path / "downloaded-model.zip")

    async def exercise():
        schema = "test_worker_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            store = Store(engine)
            dataset_id, run_id = str(uuid4()), str(uuid4())
            result = validate(export_zip, tmp_path / "validated")
            result["objectKey"] = "validated/source.zip"
            await store.submit(dataset_id, "validate", {}, "source")
            job = await store.claim()
            await store.finish(dataset_id, job["owner"], result=result)
            await store.submit(run_id, "train", {"sourceJobId": dataset_id, "epochs": 1}, "train")
            worker = Worker(Settings(workspace=tmp_path / "workspace"), store, Storage())
            await worker.run_job(await store.claim())
            assert (await store.get(run_id))["status"] == "queued"
            first_events = await store.events(run_id, 0)
            assert sum(event["kind"] == "metric" for event in first_events) == 1
            # A new Worker instance uses the persisted attempt checkpoint, without training again.
            await Worker(worker.settings, Store(engine), worker.storage).run_job(
                await store.claim()
            )
            final = await store.get(run_id)
            assert final["status"] == "completed" and final["attempt"] == 2
            assert final["result"]["report"]["independentReload"] is True
            events = await store.events(run_id, 0)
            assert sum(event["kind"] == "metric" for event in events) == 1
            assert any("Resumed sealed" in str(event["data"]) for event in events)
            assert (tmp_path / "downloaded-model.zip").is_file()
            cancelled_id = str(uuid4())
            await store.submit(cancelled_id, "train", {}, "cancel-during-event")

            class CancelAtEvent(Worker):
                async def execute(self, job):
                    await self.store.cancel(job["id"])
                    await self.store.event(job["id"], job["owner"], "metric", {"epoch": 1})
                    raise AssertionError("cancelled event must reject the old executor")

            await CancelAtEvent(worker.settings, store, worker.storage).run_job(await store.claim())
            assert (await store.get(cancelled_id))["status"] == "cancelled"

        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
