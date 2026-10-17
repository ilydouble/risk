"""Dataset clearing removes only owned records and leaves no automatic import source."""

import asyncio
import hashlib
import os
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_enterprise_data import Remote, Storage, artifact_content

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.modeling.api.schemas import RequestClearDataset
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
from risk_api.modules.modeling.enterprise_data import FORMAT
from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import (
    Dataset,
    Dispatch,
    EnterpriseImport,
    EnterprisePrediction,
    EnterpriseRecord,
    ModelVersion,
    Run,
)


def test_clear_requires_explicit_confirmation_and_name():
    for extra in ({}, {"confirm": False, "name": "UK"}, {"confirm": True, "name": ""}):
        with pytest.raises(ValidationError):
            RequestClearDataset.model_validate({"datasetId": str(uuid4()), **extra})


def test_clear_is_owned_atomic_and_allows_reimport():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for dataset clearing")

    async def exercise():
        schema = "test_clear_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        tables = (User, Dataset, Run, ModelVersion, Dispatch, EnterpriseImport,
                  EnterpriseRecord, EnterprisePrediction)
        try:
            async with engine.begin() as connection:
                for model in tables:
                    await connection.run_sync(model.__table__.create)
            async with sessions() as session:
                owner, other = str(uuid4()), str(uuid4())
                session.add(User(id=owner, username=owner, password_hash="x", display_name="T"))
                await session.commit()
                contract, content = artifact_content("a" * 64)
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(Storage(content)), Remote()
                )
                enterprises = EnterpriseService(modeling)

                async def upload():
                    identity = str(uuid4())
                    session.add(Dataset(
                        id=identity, owner_id=owner, name="英国", filename="uk.zip",
                        object_key="uploads/" + identity, content_type="application/zip",
                        size=len(content), confirmed=True, execution={
                            "status": "completed", "result": {
                                "datasetContract": contract, "sha256": "a" * 64,
                                "enterpriseData": {"counts": {
                                    "company": 1, "person": 2, "edge": 1,
                                    "hyperedge": 1, "event": 1,
                                }},
                                "enterpriseArtifact": {"format": FORMAT, "kind": "file",
                                    "size": len(content),
                                    "sha256": hashlib.sha256(content).hexdigest(),
                                    "objectKey": identity},
                            },
                        },
                    ))
                    await session.commit()
                    await enterprises.import_dataset(owner, identity)
                    return identity

                identity, untouched = await upload(), await upload()
                run_id, retry_id, model_id = [str(uuid4()) for _ in range(3)]
                session.add(Run(id=run_id, owner_id=owner, dataset_id=identity, name="run",
                                request_key=run_id, configuration={},
                                execution={"status": "running"}))
                await session.commit()
                for user, name, code in (
                    (other, "英国", "MODELING_RESOURCE_NOT_FOUND"),
                    (owner, "wrong", "MODELING_CONFIRMATION_MISMATCH"),
                    (owner, "英国", "MODELING_DATASET_BUSY"),
                ):
                    with pytest.raises(AppError) as denied:
                        await modeling.clear_dataset(user, identity, name)
                    assert denied.value.code == code
                    await session.rollback()
                    assert await session.get(EnterpriseImport, identity)
                run = await session.get(Run, run_id)
                run.execution = {"status": "completed"}
                session.add(Run(id=retry_id, owner_id=owner, dataset_id=identity, name="retry",
                                request_key=retry_id, retry_of=run_id, configuration={},
                                execution={"status": "failed"}))
                await session.commit()
                session.add(ModelVersion(id=model_id, owner_id=owner, run_id=run_id,
                                         name="version", artifact={}))
                await session.commit()
                session.add(EnterprisePrediction(model_id=model_id, company_id="c-1",
                                                 dataset_id=identity, result={}))
                for job in (identity, run_id, retry_id, untouched):
                    session.add(Dispatch(id=job, operation="submit", payload={"jobId": job},
                                         request_id="test", delivered=True))
                await session.commit()
                await modeling.clear_dataset(owner, identity, "英国")
                assert await session.get(Dataset, identity) is None
                for model in (Run, ModelVersion, EnterprisePrediction):
                    assert await session.scalar(select(func.count()).select_from(model)) == 0
                for model in (EnterpriseImport, EnterpriseRecord):
                    assert await session.scalar(select(func.count()).select_from(model).where(
                        model.dataset_id == identity
                    )) == 0
                assert (await enterprises.page(
                    owner, untouched, "company", "", None, None, None, 1, 20
                ))["total"] == 1
                assert list(await session.scalars(select(Dispatch.id))) == [untouched]
                sources = await EnterpriseBrowseService(modeling).sources(owner, 1, 100)
                assert [item["id"] for item in sources["items"]] == [untouched]
                replacement = await upload()
                assert (await enterprises.page(
                    owner, replacement, "company", "", None, None, None, 1, 20
                ))["total"] == 1
                pending = await session.get(Dataset, replacement)
                pending.execution = {"status": "running"}
                await session.commit()
                with pytest.raises(AppError) as busy:
                    await modeling.clear_dataset(owner, replacement, "英国")
                assert busy.value.code == "MODELING_DATASET_BUSY"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
