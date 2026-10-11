import asyncio
import os
import shutil
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from model_service.execution.worker import Worker
from model_service.modules.jobs.model import Base
from model_service.modules.jobs.repository import Store
from model_service.modules.models.service import Runtime
from model_service.shared.config import Settings
from riskgnn.dataset_adapters.registry import inspect


def test_artifact_upload_retry_reuses_independently_tested_checkpoint(export_zip, tmp_path):
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for worker recovery acceptance")

    class Storage:
        failures = 1
        objects = {}

        async def download_file(self, _key, target):
            shutil.copy2(self.objects.get(_key, export_zip), target)

        async def upload_file(self, key, source, **_kwargs):
            if self.failures:
                self.failures -= 1
                raise OSError("transient upload failure")
            target = tmp_path / (
                "downloaded-model.zip" if "/train/" in str(source) else "downloaded-report.zip"
            )
            shutil.copy2(source, target)
            self.objects[key] = target

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
            result = inspect(export_zip, tmp_path / "validated")
            result["objectKey"] = "validated/source.zip"
            await store.submit(dataset_id, "validate", {}, "source")
            job = await store.claim()
            await store.finish(dataset_id, job["owner"], result=result)
            worker = Worker(Settings(workspace=tmp_path / "workspace"), store, Storage())
            runtime = Runtime(store, worker.storage, worker.settings)
            snapshot = await runtime.configuration(
                dataset_id,
                {
                    "epochs": 1,
                    "dataset": {"target_count": 30},
                },
                None,
                "configuration-request",
            )
            await store.submit(
                run_id,
                "train",
                {
                    "sourceJobId": dataset_id,
                    "configuration": snapshot,
                },
                "train",
            )
            await worker.run_job(await store.claim())
            assert (await store.get(run_id))["status"] == "queued"
            first_events = await store.events(run_id, 0)
            assert (
                sum(
                    event["kind"] == "metric" and event["data"].get("group") == "train"
                    for event in first_events
                )
                == 1
            )
            # A new Worker instance uses the persisted attempt checkpoint, without training again.
            await Worker(worker.settings, Store(engine), worker.storage).run_job(
                await store.claim()
            )
            final = await store.get(run_id)
            assert final["status"] == "completed" and final["attempt"] == 2
            assert final["result"]["report"]["independentReload"] is True
            assert final["result"]["effectiveConfig"] == snapshot["resolvedParameters"]
            assert final["result"]["actualCounts"]["targets"] == 30
            events = await store.events(run_id, 0)
            assert (
                sum(
                    event["kind"] == "metric" and event["data"].get("group") == "train"
                    for event in events
                )
                == 1
            )
            assert any("Resumed sealed" in str(event["data"]) for event in events)
            assert (tmp_path / "downloaded-model.zip").is_file()
            runtime = Runtime(store, worker.storage, worker.settings)
            ids = final["result"]["companies"][:2]
            predictions = await runtime.predict(run_id, ids, "prediction-request")
            assert [item["companyId"] for item in predictions] == ids
            with pytest.raises(KeyError):
                await runtime.predict(run_id, ["unknown"], "prediction-request")
            generic_id = str(uuid4())
            await store.submit(
                generic_id,
                "execute",
                {
                    "runtime_id": "riskgnn",
                    "runtime_version": "2",
                    "operation": "inspect",
                    "inputs": {
                        "dataset": {
                            "object_key": "uploads/test/source.zip",
                            "sha256": result["sha256"],
                            "format": "zip",
                        }
                    },
                    "parameters": {},
                },
                "generic-request",
            )
            await worker.run_job(await store.claim())
            inspected = await store.get(generic_id)
            assert inspected["status"] == "completed"
            assert inspected["result"]["data"]["compatibility"] == "compatible"
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
