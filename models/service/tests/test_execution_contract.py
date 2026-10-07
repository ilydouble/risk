"""PostgreSQL tests use a fresh schema, never the service's execution tables."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from service.execution.model import Base, Job
from service.execution.store import LostLease, Store
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import create_async_engine


def test_idempotency_fencing_retry_cancellation_and_event_replay():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL to run the PostgreSQL execution contract")

    async def exercise():
        schema = "test_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            store = Store(engine)
            identity = str(uuid4())
            await store.submit(identity, "validate", {"objectKey": "input.zip"}, "request-one")
            await store.submit(identity, "validate", {"objectKey": "input.zip"}, "request-two")
            with pytest.raises(ValueError):
                await store.submit(identity, "train", {}, "conflict")
            first = await store.claim()
            assert first and await store.claim() is None
            assert await store.heartbeat(identity, first["owner"])
            await store.event(identity, first["owner"], "metric", {"epoch": 1})
            # Simulate a killed worker. A new service instance must recover the durable lease.
            async with engine.begin() as connection:
                await connection.execute(
                    update(Job)
                    .where(Job.id == identity)
                    .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
                )
            second = await Store(engine).claim()
            assert second and second["attempt"] == 2
            assert not await store.finish(identity, first["owner"], result={"stale": True})
            assert not await store.heartbeat(identity, first["owner"])
            with pytest.raises(LostLease):
                await store.event(identity, first["owner"], "metric", {})
            await store.finish(identity, second["owner"], error="network", retryable=True)
            third = await store.claim()
            assert third and third["attempt"] == 3
            await store.finish(identity, third["owner"], error="network", retryable=True)
            assert (await store.get(identity))["status"] == "failed"
            assert await store.claim() is None
            events = await Store(engine).events(identity, 0)
            assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
            assert await store.events(identity, 2) == events[2:]
            for queued in (True, False):
                new_id = str(uuid4())
                await store.submit(new_id, "train", {}, "cancel")
                claimed = None if queued else await store.claim()
                await store.cancel(new_id)
                if claimed:
                    assert not await store.heartbeat(new_id, claimed["owner"])
                    await store.finish(new_id, claimed["owner"], result={"mustNotPublish": True})
                snapshot = await store.get(new_id)
                assert snapshot["status"] == "cancelled" and snapshot["result"] == {}
            assert await store.claim() is None
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
