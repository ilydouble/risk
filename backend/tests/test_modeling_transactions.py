"""Business ownership and delivery contracts against an isolated PostgreSQL schema."""

import asyncio
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.modeling.dispatch import deliver_one
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import Dataset, Dispatch, ModelVersion, Run


class Remote:
    def __init__(self):
        self.calls = []
        self.available = False

    async def call(self, action, body, request_id=""):
        self.calls.append((action, body, request_id))
        if not self.available:
            raise AppError(503, "MODEL_SERVICE_UNAVAILABLE", "offline")
        return {"status": "queued"}


class Storage:
    async def stat(self, _key):
        return SimpleNamespace(size=123)


def test_business_outbox_idempotency_ownership_and_publication():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for the PostgreSQL business contract")

    async def exercise():
        schema = "test_business_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        remote = Remote()
        try:
            async with engine.begin() as connection:
                for model in (User, Dataset, Run, ModelVersion, Dispatch):
                    await connection.run_sync(model.__table__.create)
            async with sessions() as session:
                owner, other, dataset_id = [str(uuid4()) for _ in range(3)]
                session.add(
                    User(id=owner, username="owner", password_hash="hash", display_name="Owner")
                )
                await session.commit()
                source = Dataset(
                    id=dataset_id,
                    owner_id=owner,
                    name="test",
                    filename="source.zip",
                    object_key="input",
                    content_type="application/zip",
                    size=123,
                )
                session.add(source)
                await session.commit()
                service = ModelingService(
                    ModelingRepository(session), ModelingStorage(Storage()), remote
                )
                await service.complete_upload(owner, dataset_id, "request")
                await service.complete_upload(owner, dataset_id, "request-again")
                assert len(list(await session.scalars(select(Dispatch)))) == 1
                with pytest.raises(AppError) as error:
                    await service.get_dataset(other, dataset_id)
                assert error.value.status == 404
                await session.rollback()
                source = await session.get(Dataset, dataset_id)
                source.execution = {"status": "completed"}
                await session.commit()
                key = str(uuid4())
                run = await service.create_run(
                    owner, dataset_id, "experiment", key, 2, "gateway-id"
                )
                again = await service.create_run(
                    owner, dataset_id, "experiment", key, 2, "other-id"
                )
                assert again.id == run.id
                assert run.configuration["runnerId"] == "riskgnn-node-edge"
                dispatch = await session.get(Dispatch, run.id)
                assert dispatch.payload["payload"]["runnerId"] == "riskgnn-node-edge"
                with pytest.raises(AppError) as conflict:
                    await service.create_run(
                        owner, dataset_id, "experiment", key, 2, "conflict",
                        runner_id="riskgnn-node-only",
                    )
                assert conflict.value.code == "MODELING_STATE_INVALID"
                source.execution = {
                    "status": "completed", "result": {"supportedRunnerIds": []}
                }
                await session.commit()
                with pytest.raises(AppError) as incompatible:
                    await service.create_run(
                        owner, dataset_id, "bundle", str(uuid4()), 2, "incompatible"
                    )
                assert incompatible.value.code == "MODELING_MODEL_INCOMPATIBLE"
                assert incompatible.value.status == 422
                assert len(list(await session.scalars(select(Run)))) == 1
                with pytest.raises(AppError):
                    await service.create_run(owner, dataset_id, "different", key, 2, "conflict")
                assert len(list(await session.scalars(select(Dispatch)))) == 2
                # Atomic transaction: no partial run or outbox row survives a failed commit.
                await session.rollback()
                bad_id = str(uuid4())
                session.add(
                    Run(
                        id=bad_id,
                        owner_id="missing",
                        dataset_id=dataset_id,
                        name="bad",
                        request_key=str(uuid4()),
                        configuration={"epochs": 2},
                    )
                )
                service.enqueue(bad_id, "train", {}, "bad")
                from sqlalchemy.exc import IntegrityError

                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
                assert await session.get(Dispatch, bad_id) is None
                run = await session.scalar(select(Run).where(Run.request_key == key))
                run.execution = {
                    "status": "completed",
                    "result": {"sha256": "digest", "report": {"independentReload": True}},
                }
                await session.commit()
                first = await service.publish(owner, run.id, "version")
                second = await service.publish(owner, run.id, "new name")
                assert first.id == second.id and second.name == "version"
                with pytest.raises(AppError):
                    await service.repository.version(other, first.id)
            assert await deliver_one(sessions, remote)
            async with sessions.begin() as session:
                pending = list(await session.scalars(select(Dispatch)))
                assert not any(row.delivered for row in pending)
                await session.execute(update(Dispatch).values(available_at=datetime.now(UTC)))
            remote.available = True
            assert await deliver_one(sessions, remote)
            assert await deliver_one(sessions, remote)
            assert not await deliver_one(sessions, remote)
            assert any(call[2] == "gateway-id" for call in remote.calls)
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
