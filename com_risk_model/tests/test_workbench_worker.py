from __future__ import annotations

import asyncio
from typing import Any

import pytest

from workbench.worker import Job, JobStore, ModelingWorker


class _Mappings:
    def __init__(self, row: dict[str, Any] | None):
        self.row = row

    def mappings(self) -> _Mappings:
        return self

    def first(self) -> dict[str, Any] | None:
        row, self.row = self.row, None
        return row


class _Connection:
    def __init__(self, row: dict[str, Any] | None = None):
        self.result = _Mappings(row)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, parameters: dict[str, Any]) -> _Mappings:
        required = set(statement.compile().params)
        missing = required.difference(parameters)
        assert not missing, f"missing SQL parameters: {missing}"
        self.calls.append((str(statement), parameters))
        return self.result


class _Transaction:
    def __init__(self, connection: _Connection):
        self.connection = connection

    async def __aenter__(self) -> _Connection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None


class _Engine:
    def __init__(self, row: dict[str, Any] | None = None):
        self.connection = _Connection(row)

    def begin(self) -> _Transaction:
        return _Transaction(self.connection)


def _job(*, attempt_count: int = 1, max_attempts: int = 3) -> Job:
    return Job(
        id="job-1",
        owner_id="owner-1",
        dataset_id="dataset-1",
        experiment_id=None,
        kind="analyze_bundle",
        payload={"objectKey": "bundle.zip"},
        attempt_count=attempt_count,
        max_attempts=max_attempts,
    )


def test_claim_uses_skip_locked_lease_and_bound_json() -> None:
    row = vars(_job())
    engine = _Engine(row)
    store = JobStore(engine, "worker-1", 60)  # type: ignore[arg-type]

    claimed = asyncio.run(store.claim())

    assert claimed == _job()
    statement, parameters = engine.connection.calls[0]
    assert "FOR UPDATE SKIP LOCKED" in statement
    assert "lease_until < now()" in statement
    assert parameters["starting_progress"] == '{"stage": "starting", "percent": 1}'


@pytest.mark.parametrize(("attempt", "expected"), [(1, "queued"), (3, "failed")])
def test_failure_retries_twice_then_becomes_terminal(attempt: int, expected: str) -> None:
    engine = _Engine()
    store = JobStore(engine, "worker-1", 60)  # type: ignore[arg-type]

    asyncio.run(store.fail(_job(attempt_count=attempt), RuntimeError("storage unavailable")))

    assert engine.connection.calls[0][1]["status"] == expected
    assert engine.connection.calls[1][1]["status"] == expected


class _FailingStore:
    def __init__(self):
        self.failed: list[tuple[Job, Exception]] = []

    async def claim(self) -> Job:
        return _job()

    async def fail(self, job: Job, error: Exception) -> None:
        self.failed.append((job, error))


class _FailingWorker(ModelingWorker):
    def __init__(self):
        self.store = _FailingStore()  # type: ignore[assignment]

    async def _analyze(self, job: Job) -> None:
        raise RuntimeError("RustFS unavailable")


def test_storage_failure_is_recorded_instead_of_crashing_worker() -> None:
    worker = _FailingWorker()

    assert asyncio.run(worker.run_once()) is True
    assert len(worker.store.failed) == 1  # type: ignore[attr-defined]
    assert str(worker.store.failed[0][1]) == "RustFS unavailable"  # type: ignore[attr-defined]
