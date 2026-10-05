from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from stellarmesh_objectstorage import AsyncClient, ClientConfig

from workbench.analysis import analyze_bundle
from workbench.data import BundleData, load_bundle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    storage_bucket: str
    storage_endpoint: str
    storage_region: str
    storage_access_key: str
    storage_secret_key: str
    poll_seconds: float = 2.0
    lease_seconds: int = 300
    max_bundle_bytes: int = 512 * 1024 * 1024

    @classmethod
    def from_env(cls) -> WorkerSettings:
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://risk:local-risk-db-password@localhost:5432/risk",
            ),
            storage_bucket=os.getenv("STORAGE_BUCKET", "risk-documents"),
            storage_endpoint=os.getenv("STORAGE_ENDPOINT", "http://127.0.0.1:19000"),
            storage_region=os.getenv("STORAGE_REGION", "us-east-1"),
            storage_access_key=os.getenv("STORAGE_ACCESS_KEY", "RISKDOCUMENTSAPP2026"),
            storage_secret_key=os.getenv(
                "STORAGE_SECRET_KEY", "local-rustfs-app-change-me-2026"
            ),
            poll_seconds=float(os.getenv("MODELING_WORKER_POLL_SECONDS", "2")),
            lease_seconds=int(os.getenv("MODELING_WORKER_LEASE_SECONDS", "300")),
        )


@dataclass(frozen=True)
class Job:
    id: str
    owner_id: str
    dataset_id: str
    experiment_id: str | None
    kind: str
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int


class JobStore:
    def __init__(self, engine: AsyncEngine, worker_id: str, lease_seconds: int):
        self.engine = engine
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    async def claim(self) -> Job | None:
        lease_until = datetime.now(UTC) + timedelta(seconds=self.lease_seconds)
        statement = text(
            """
            WITH candidate AS (
                SELECT id
                FROM modeling_jobs
                WHERE attempt_count < max_attempts
                  AND (
                    status = 'queued'
                    OR (status = 'running' AND lease_until < now())
                  )
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE modeling_jobs AS job
            SET status = 'running',
                attempt_count = attempt_count + 1,
                lease_owner = :worker_id,
                lease_until = :lease_until,
                error = NULL,
                progress = CAST(:starting_progress AS jsonb),
                updated_at = now()
            FROM candidate
            WHERE job.id = candidate.id
            RETURNING job.id, job.owner_id, job.dataset_id, job.experiment_id,
                      job.kind, job.payload, job.attempt_count, job.max_attempts
            """
        )
        async with self.engine.begin() as connection:
            row = (
                await connection.execute(
                    statement,
                    {
                        "worker_id": self.worker_id,
                        "lease_until": lease_until,
                        "starting_progress": json.dumps({"stage": "starting", "percent": 1}),
                    },
                )
            ).mappings().first()
            if row is None:
                return None
            is_analysis = row["kind"] == "analyze_bundle"
            target = "modeling_datasets" if is_analysis else "modeling_experiments"
            target_id = row["dataset_id"] if is_analysis else row["experiment_id"]
            await connection.execute(
                text(
                    f"UPDATE {target} SET status='running', "
                    "started_at=COALESCE(started_at, now()), "
                    "progress=CAST(:progress AS jsonb), error=NULL "
                    "WHERE id=:target_id"
                ),
                {
                    "target_id": target_id,
                    "progress": json.dumps({"stage": "starting", "percent": 1}),
                },
            )
        return Job(**dict(row))

    async def progress(self, job: Job, stage: str, percent: int) -> None:
        progress = json.dumps({"stage": stage, "percent": percent})
        lease_until = datetime.now(UTC) + timedelta(seconds=self.lease_seconds)
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE modeling_jobs SET progress=CAST(:progress AS jsonb), "
                    "lease_until=:lease_until, updated_at=now() "
                    "WHERE id=:id AND lease_owner=:worker_id AND status='running'"
                ),
                {
                    "id": job.id,
                    "worker_id": self.worker_id,
                    "progress": progress,
                    "lease_until": lease_until,
                },
            )
            target = "modeling_datasets" if job.kind == "analyze_bundle" else "modeling_experiments"
            target_id = job.dataset_id if job.kind == "analyze_bundle" else job.experiment_id
            await connection.execute(
                text(f"UPDATE {target} SET progress=CAST(:progress AS jsonb) WHERE id=:target_id"),
                {"target_id": target_id, "progress": progress},
            )

    async def complete_analysis(
        self, job: Job, data: BundleData, analysis: dict[str, Any]
    ) -> None:
        manifest = data.metadata.model_dump(mode="json", by_alias=True)
        values = {
            "job_id": job.id,
            "dataset_id": job.dataset_id,
            "manifest": json.dumps(manifest, ensure_ascii=False),
            "task_type": data.metadata.task_type,
            "sample_unit": data.metadata.sample_unit,
            "capabilities": json.dumps(data.capabilities),
            "validation": json.dumps(data.validation),
            "analysis": json.dumps(analysis, ensure_ascii=False),
            "row_count": len(data.samples),
            "column_count": len(data.samples.columns),
            "ready_progress": json.dumps({"stage": "ready", "percent": 100}),
            "completed_progress": json.dumps({"stage": "completed", "percent": 100}),
        }
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE modeling_datasets
                    SET status='ready', schema_version=1, task_type=:task_type,
                        sample_unit=:sample_unit, manifest=CAST(:manifest AS jsonb),
                        capabilities=CAST(:capabilities AS jsonb),
                        validation=CAST(:validation AS jsonb), analysis=CAST(:analysis AS jsonb),
                        preview=NULL, row_count=:row_count, column_count=:column_count,
                        progress=CAST(:ready_progress AS jsonb),
                        error=NULL, finished_at=now()
                    WHERE id=:dataset_id
                    """
                ),
                values,
            )
            await connection.execute(
                text(
                    "UPDATE modeling_jobs SET status='completed', lease_owner=NULL, "
                    "lease_until=NULL, "
                    "progress=CAST(:completed_progress AS jsonb), "
                    "error=NULL, updated_at=now() WHERE id=:job_id"
                ),
                values,
            )

    async def experiment_request(self, job: Job) -> dict[str, Any]:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT configuration, feature_columns, requested_models, target_name "
                        "FROM modeling_experiments WHERE id=:id AND dataset_id=:dataset_id"
                    ),
                    {"id": job.experiment_id, "dataset_id": job.dataset_id},
                )
            ).mappings().first()
        if row is None:
            raise ValueError("experiment does not exist")
        return dict(row)

    async def complete_experiment(
        self,
        job: Job,
        selected_features: list[str],
        results: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> None:
        values = {
            "job_id": job.id,
            "experiment_id": job.experiment_id,
            "selected_features": json.dumps(selected_features),
            "results": json.dumps(results, ensure_ascii=False),
            "artifacts": json.dumps(artifacts),
            "completed_progress": json.dumps({"stage": "completed", "percent": 100}),
        }
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE modeling_experiments
                    SET status='completed', selected_features=CAST(:selected_features AS jsonb),
                        results=CAST(:results AS jsonb), artifacts=CAST(:artifacts AS jsonb),
                        progress=CAST(:completed_progress AS jsonb),
                        error=NULL, finished_at=now()
                    WHERE id=:experiment_id
                    """
                ),
                values,
            )
            await connection.execute(
                text(
                    "UPDATE modeling_jobs SET status='completed', lease_owner=NULL, "
                    "lease_until=NULL, "
                    "progress=CAST(:completed_progress AS jsonb), "
                    "error=NULL, updated_at=now() WHERE id=:job_id"
                ),
                values,
            )

    async def fail(self, job: Job, error: Exception) -> None:
        retry = job.attempt_count < job.max_attempts
        status = "queued" if retry else "failed"
        message = str(error)[:4000]
        target = "modeling_datasets" if job.kind == "analyze_bundle" else "modeling_experiments"
        target_id = job.dataset_id if job.kind == "analyze_bundle" else job.experiment_id
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE modeling_jobs SET status=:status, lease_owner=NULL, lease_until=NULL, "
                    "error=:error, progress=CAST(:progress AS jsonb), updated_at=now() WHERE id=:id"
                ),
                {
                    "id": job.id,
                    "status": status,
                    "error": message,
                    "progress": json.dumps(
                        {"stage": "retrying" if retry else "failed", "percent": 0}
                    ),
                },
            )
            await connection.execute(
                text(
                    f"UPDATE {target} SET status=:status, error=:error, "
                    "progress=CAST(:progress AS jsonb), "
                    "finished_at=CASE WHEN :terminal THEN now() ELSE NULL END "
                    "WHERE id=:target_id"
                ),
                {
                    "target_id": target_id,
                    "status": status,
                    "terminal": not retry,
                    "error": message,
                    "progress": json.dumps(
                        {"stage": "retrying" if retry else "failed", "percent": 0}
                    ),
                },
            )


class ModelingWorker:
    def __init__(self, settings: WorkerSettings, engine: AsyncEngine, storage: AsyncClient):
        worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.settings = settings
        self.store = JobStore(engine, worker_id, settings.lease_seconds)
        self.storage = storage

    async def run_once(self) -> bool:
        job = await self.store.claim()
        if job is None:
            return False
        try:
            if job.kind == "analyze_bundle":
                await self._analyze(job)
            elif job.kind == "train_experiment":
                await self._train(job)
            else:
                raise ValueError(f"unknown modeling job kind: {job.kind}")
        except Exception as error:
            logger.exception("modeling worker job failed", extra={"job_id": job.id})
            await self.store.fail(job, error)
        return True

    async def _download(self, object_key: str) -> bytes:
        payload = bytearray()
        async with self.storage.open_object(object_key) as stream:
            # Network streams may return a short read before EOF, even for a large read size.
            async for chunk in stream.iter_chunks():
                if len(payload) + len(chunk) > self.settings.max_bundle_bytes:
                    raise ValueError("bundle exceeds worker size limit")
                payload.extend(chunk)
        return bytes(payload)

    async def _analyze(self, job: Job) -> None:
        await self.store.progress(job, "downloading", 10)
        payload = await self._download(str(job.payload["objectKey"]))
        await self.store.progress(job, "validating", 30)
        data = await asyncio.to_thread(load_bundle, payload)
        await self.store.progress(job, "profiling", 55)
        analysis = await asyncio.to_thread(analyze_bundle, data)
        await self.store.complete_analysis(job, data, analysis)

    async def _train(self, job: Job) -> None:
        from workbench.training import run_experiment

        await run_experiment(self, job)


async def run_worker(settings: WorkerSettings, *, once: bool) -> int:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", settings.storage_access_key)
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", settings.storage_secret_key)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    config = ClientConfig(
        bucket=settings.storage_bucket,
        region=settings.storage_region,
        endpoint=settings.storage_endpoint,
        use_path_style=True,
    )
    try:
        async with AsyncClient(config) as storage:
            worker = ModelingWorker(settings, engine, storage)
            while True:
                handled = await worker.run_once()
                if once:
                    return 0 if handled else 2
                if not handled:
                    await asyncio.sleep(settings.poll_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local metadata-driven modeling worker")
    parser.add_argument("--once", action="store_true", help="claim at most one job")
    arguments = parser.parse_args()
    logging.basicConfig(level=os.getenv("RISK_LOG_LEVEL", "INFO"))
    try:
        exit_code = asyncio.run(run_worker(WorkerSettings.from_env(), once=arguments.once))
    except KeyboardInterrupt:
        exit_code = 0
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
