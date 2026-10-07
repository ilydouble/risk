from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from service.execution.model import Attempt, Event, Job


class LostLease(Exception):
    pass


class Store:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def submit(self, job_id: str, kind: str, payload: dict, request_id: str) -> None:
        async with self.sessions.begin() as session:
            await session.execute(
                insert(Job)
                .values(id=job_id, kind=kind, payload=payload, request_id=request_id)
                .on_conflict_do_nothing(index_elements=[Job.id])
            )
            job = await session.get(Job, job_id)
            assert job is not None
            if job.kind != kind or job.payload != payload:
                raise ValueError("Operation ID already used for different input")

    async def get(self, job_id: str) -> dict[str, Any]:
        async with self.sessions() as session:
            job = await session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            attempts = list(
                (
                    await session.scalars(
                        select(Attempt).where(Attempt.job_id == job_id).order_by(Attempt.number)
                    )
                ).all()
            )
            return {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "stage": job.stage,
                "attempt": job.attempt,
                "result": job.result,
                "error": job.error,
                "cancelRequested": job.cancel_requested,
                "payload": job.payload,
                "requestId": job.request_id,
                "attempts": [
                    {
                        "number": a.number,
                        "status": a.status,
                        "error": a.error,
                        "startedAt": a.started_at.isoformat(),
                        "finishedAt": a.finished_at.isoformat() if a.finished_at else None,
                    }
                    for a in attempts
                ],
            }

    @staticmethod
    def _event(session, job: Job, kind: str, data: dict) -> None:
        job.next_event += 1
        session.add(
            Event(job_id=job.id, sequence=job.next_event, attempt=job.attempt, kind=kind, data=data)
        )

    async def claim(self) -> dict | None:
        now = datetime.now(UTC)
        async with self.sessions.begin() as session:
            expired = list(
                (
                    await session.scalars(
                        select(Job)
                        .where(Job.status == "running", Job.lease_until < now)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            job: Job | None
            for expired_job in expired:
                job = expired_job
                attempt = await session.get(Attempt, job.lease_owner)
                if attempt:
                    attempt.status, attempt.error, attempt.finished_at = (
                        "failed",
                        "Lease expired",
                        now,
                    )
                job.status = (
                    "cancelled"
                    if job.cancel_requested
                    else "failed"
                    if job.attempt >= 3
                    else "queued"
                )
                job.error = "Worker lease expired"
                job.lease_owner, job.lease_until = None, None
                self._event(session, job, "state", {"status": job.status, "reason": job.error})
            await session.flush()
            job = await session.scalar(
                select(Job)
                .where(Job.status == "queued")
                .order_by(Job.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.attempt += 1
            owner = str(uuid4())
            job.lease_owner, job.lease_until = owner, now + timedelta(seconds=60)
            job.status, job.stage, job.error = "running", "starting", None
            session.add(Attempt(id=owner, job_id=job.id, number=job.attempt))
            self._event(session, job, "state", {"status": "running", "stage": "starting"})
            return {
                "id": job.id,
                "kind": job.kind,
                "payload": job.payload,
                "attempt": job.attempt,
                "owner": owner,
                "requestId": job.request_id,
            }

    async def heartbeat(self, job_id: str, owner: str) -> bool:
        async with self.sessions.begin() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if (
                not job
                or job.lease_owner != owner
                or job.status != "running"
                or (job.lease_until is None or job.lease_until <= datetime.now(UTC))
                or job.cancel_requested
            ):
                return False
            job.lease_until = datetime.now(UTC) + timedelta(seconds=60)
            return True

    async def event(self, job_id: str, owner: str, kind: str, data: dict) -> None:
        async with self.sessions.begin() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if (
                not job
                or job.lease_owner != owner
                or job.status != "running"
                or (job.lease_until is None or job.lease_until <= datetime.now(UTC))
                or job.cancel_requested
            ):
                raise LostLease()
            if kind == "state":
                job.stage = data["stage"]
            self._event(session, job, kind, data)

    async def finish(
        self,
        job_id: str,
        owner: str,
        *,
        result: dict | None = None,
        error: str | None = None,
        retryable: bool = False,
    ) -> bool:
        async with self.sessions.begin() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if (
                not job
                or job.lease_owner != owner
                or job.status != "running"
                or (job.lease_until is None or job.lease_until <= datetime.now(UTC))
            ):
                return False
            status = (
                "cancelled"
                if job.cancel_requested
                else "completed"
                if error is None
                else "queued"
                if retryable and job.attempt < 3
                else "failed"
            )
            job.status, job.error = status, error
            if status == "completed":
                job.result = result or {}
            job.lease_owner, job.lease_until = None, None
            attempt = await session.get(Attempt, owner)
            assert attempt is not None
            attempt.status = "failed" if status == "queued" else status
            attempt.error, attempt.finished_at = error, datetime.now(UTC)
            self._event(session, job, "state", {"status": status, "error": error})
            return True

    async def cancel(self, job_id: str) -> None:
        async with self.sessions.begin() as session:
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job is None:
                raise KeyError(job_id)
            if job.status in {"completed", "failed", "cancelled"}:
                return
            job.cancel_requested = True
            if job.status == "queued":
                job.status = "cancelled"
            self._event(session, job, "state", {"status": job.status, "cancelRequested": True})

    async def events(self, job_id: str, after: int) -> list[dict]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Event)
                .where(Event.job_id == job_id, Event.sequence > after)
                .order_by(Event.sequence)
                .limit(200)
            )
            return [
                {
                    "sequence": row.sequence,
                    "attempt": row.attempt,
                    "kind": row.kind,
                    "data": row.data,
                    "createdAt": row.created_at.isoformat(),
                }
                for row in rows
            ]
