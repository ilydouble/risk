import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from model_service.modules.jobs.api.schemas import ResponseJob
from model_service.modules.jobs.repository import Store


@pytest.mark.parametrize(("status", "remaining", "alive"), [
    ("running", 60, True), ("running", -1, False), ("running", None, False),
    ("queued", None, None), ("completed", None, None),
])
def test_job_status_reports_worker_lease_independently_of_logs(status, remaining, alive):
    lease = datetime.now(UTC) + timedelta(seconds=remaining) if remaining is not None else None
    job = SimpleNamespace(
        id="job", kind="train", status=status, stage="preparing", attempt=1,
        lease_until=lease, result={}, error=None, cancel_requested=False,
        payload={}, request_id="request",
    )

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def get(self, *_):
            return job

        async def scalars(self, *_):
            return SimpleNamespace(all=lambda: [])

    store = Store(None)
    store.sessions = Session
    result = asyncio.run(store.get("job"))
    result = ResponseJob.model_validate(result).model_dump()
    assert result["workerAlive"] is alive
    assert result["heartbeatExpiresAt"] == (
        lease.isoformat() if status == "running" and lease else None
    )
