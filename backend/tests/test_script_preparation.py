import asyncio
import base64
import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from stellarmesh_objectstorage import StorageError

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.data_prep import script_delivery, script_service
from risk_api.modules.data_prep.model import Preparation, ScriptPreparation, ScriptPreparationRun
from risk_api.modules.data_prep.script_service import (
    ScriptPreparationService,
    check_script,
    pack_inputs,
    sha,
)
from risk_api.modules.data_prep.script_worker import work_once
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import Dataset, Dispatch


@pytest.mark.parametrize("files", [
    [("../escape", b"x")], [("/escape", b"x")], [("a\\b", b"x")],
    [("a/./b", b"x")], [("a", b"1"), ("a", b"2")],
    [("a", b"1"), ("a/b", b"2")], [("empty", b"")],
])
def test_input_archive_rejects_ambiguous_paths(files):
    with pytest.raises(AppError):
        pack_inputs(files)


def test_preserves_input_bytes_and_checks_python_without_executing():
    source, files = pack_inputs([("raw.csv", b"id\n001\n")])
    with ZipFile(io.BytesIO(source)) as archive:
        assert archive.read("raw.csv") == b"id\n001\n"
    assert files[0]["sha256"] == sha(b"id\n001\n")
    check_script("raise RuntimeError('not executed')")
    with pytest.raises(AppError) as error:
        check_script("if :")
    assert error.value.code == "DATA_PREP_SCRIPT_INVALID"


def test_owner_revision_frozen_queue_and_idempotent_delivery(monkeypatch):
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires isolated PostgreSQL")

    async def run():
        schema = "script_test_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                for table in (User, Preparation, Dataset, Dispatch, ScriptPreparation,
                              ScriptPreparationRun):
                    await connection.run_sync(table.__table__.create)
            async with sessions.begin() as session:
                session.add_all([User(id=owner, username=owner, display_name=owner,
                                     password_hash="test") for owner in ("a", "b")])
            monkeypatch.setattr(script_service, "runner_call", AsyncMock(return_value={
                "items": [{"preset": "smesd"}],
            }))
            async with sessions() as session:
                service = ScriptPreparationService(session)
                task = await service.create("a", "test", "smesd", "my-dataset", "v1", "keep IDs",
                                            [("raw.csv", b"id\n001\n")])
                identity = task.id
                assert len(await service.list_tasks("a")) == 1
                assert await service.list_tasks("b") == []
                with pytest.raises(AppError):
                    await service.get("b", identity)
                await session.rollback()
                saved = await service.save("a", identity, 1, "print('version 2')", "keep IDs")
                assert saved.revision == 2
                with pytest.raises(AppError) as error:
                    await service.save("a", identity, 1, "print('stale')", "")
                assert error.value.code == "DATA_PREP_SCRIPT_STALE"
                await session.rollback()
                job = await service.enqueue("a", identity, 2)
                run_id = job.id
                assert (await service.enqueue("a", identity, 2)).id == run_id
                await service.save("a", identity, 2, "print('version 3')", "new requirement")
                with pytest.raises(AppError):
                    await service.enqueue("a", identity, 3)
                await session.rollback()
            output = io.BytesIO()
            with ZipFile(output, "w") as archive:
                archive.writestr("fixture.txt", "executor test stub")
            artifact = output.getvalue()

            async def execute(action, body):
                assert action == "run" and body["script"] == "print('version 2')"
                assert body["revision"] == 2
                assert body["requirements"] == "keep IDs"
                assert base64.b64decode(body["files"][0]["contentBase64"]) == b"id\n001\n"
                return {"status": "ready", "log": "executor completed", "error": "",
                        "artifactBase64": base64.b64encode(artifact).decode(),
                        "artifactSha256": sha(artifact), "files": [],
                        "validation": {"compatibility": "compatible"},
                        "runtimeImage": "sha256:test"}

            assert await work_once(sessions, execute)
            assert not await work_once(sessions, execute)
            async with sessions() as session:
                service = ScriptPreparationService(session)
                state = await service.state("a", identity)
                assert state["revision"] == 3 and state["runs"][0]["revision"] == 2
                assert state["runs"][0]["status"] == "ready"
                assert base64.b64decode((await service.artifact("a", identity, run_id))[
                    "contentBase64"]) == artifact
                with pytest.raises(AppError):
                    await service.artifact("b", identity, run_id)
                await session.rollback()
                storage = Mock()
                storage.presign_put = AsyncMock(return_value=SimpleNamespace(url="http://upload",
                                                                             headers={}))
                storage.stat = AsyncMock(return_value=SimpleNamespace(size=len(artifact)))
                storage.upload_bytes = AsyncMock()
                modeling = ModelingService(ModelingRepository(session), ModelingStorage(storage),
                                           Mock())
                storage.upload_bytes.side_effect = [StorageError("temporary upload failure"), None]
                with pytest.raises(AppError):
                    await script_delivery.deliver(service, modeling, "a", identity, run_id, "first")
                await session.rollback()
                pending = (await service.state("a", identity))["runs"][0]["result"]
                pending_id = pending["deliveryDatasetId"]
                assert not pending.get("deliveryCompleted")
                delivered = await script_delivery.deliver(service, modeling, "a", identity,
                                                           run_id, "test")
                assert delivered == pending_id
                assert (await service.state("a", identity))["runs"][0]["result"][
                    "deliveryCompleted"]
                assert await script_delivery.deliver(service, modeling, "a", identity,
                                                     run_id, "retry") == delivered
                assert storage.upload_bytes.await_count == 2
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 1
                dataset = await session.get(Dataset, delivered)
                assert dataset.mapping_snapshot["scriptSha256"] == sha(b"print('version 2')")
                assert dataset.confirmed
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(run())


def test_standalone_worker_registers_all_foreign_key_mappings():
    import subprocess
    import sys
    subprocess.run([sys.executable, "-c",
                    "import risk_api.modules.data_prep.script_worker; "
                    "from sqlalchemy.orm import configure_mappers; configure_mappers(); "
                    "from risk_api.shared.db import Base; "
                    "assert Base.metadata.sorted_tables"], check=True, capture_output=True)
