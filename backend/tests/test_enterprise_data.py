"""Stable import contracts: provenance, atomicity, isolation and model binding."""

import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.modeling.enterprise_data import FORMAT, records
from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import (
    Dataset,
    EnterpriseImport,
    EnterprisePrediction,
    EnterpriseRecord,
    ModelVersion,
    Run,
)


class Storage:
    def __init__(self, content):
        self.content = content
        self.reads = 0

    @asynccontextmanager
    async def open_object(self, key):
        self.reads += 1
        yield self

    async def iter_chunks(self):
        for offset in range(0, len(self.content), 71):
            yield self.content[offset : offset + 71]


class Remote:
    async def call(self, action, body, request_id=""):
        assert action == "models/predict"
        return {
            "items": [
                {"companyId": name, "probability": 0.25, "predictedLabel": 0}
                for name in body["companyIds"]
            ]
        }


def artifact_content(source_sha, *, dangling=False):
    contract = {
        "contract_version": 1,
        "dataset": {"id": "test", "version": "1"},
        "adapter": {"id": "test", "version": "1", "config": {}},
    }
    header = {
        "format": FORMAT,
        "datasetContract": contract,
        "sourceSha256": source_sha,
        "featureNames": ["revenue"],
        "target": "status",
    }
    rows = [
        {
            "kind": "company",
            "snapshot": "train",
            "nodeId": "c-1",
            "data": {"name": None, "attributes": {"revenue": None}, "label": 1},
        },
        {
            "kind": "person",
            "snapshot": "train",
            "nodeId": "p-1",
            "data": {"name": None, "attributes": {"revenue": None}},
        },
        {
            "kind": "person",
            "snapshot": "test",
            "nodeId": "p-1",
            "data": {"name": None, "attributes": {"revenue": None}},
        },
        {
            "kind": "edge",
            "snapshot": "train",
            "source": "p-1",
            "target": "missing" if dangling else "c-1",
            "data": {"relation": "director"},
        },
        {"kind": "event", "snapshot": "train", "source": "c-1", "data": {"cause": 1}},
        {"kind": "hyperedge", "snapshot": "train", "members": ["c-1"], "data": {"kind": "group"}},
    ]
    content = "\n".join(json.dumps(row) for row in [header, *rows]).encode() + b"\n"
    return contract, content


def test_interchange_rejects_invalid_identity_and_nonfinite_values(tmp_path: Path):
    _, content = artifact_content("a" * 64)
    source = tmp_path / "data.jsonl"
    source.write_bytes(content)
    parsed = list(records(source))
    assert parsed[1][1].data["attributes"]["revenue"] is None
    source.write_bytes(content.replace(b'"revenue": null', b'"revenue": NaN'))
    with pytest.raises(ValueError, match="Invalid JSON number"):
        list(records(source))
    source.write_bytes(content.replace(b'"revenue": null', b'"revenue": 1e999'))
    with pytest.raises(ValueError, match="Invalid JSON number"):
        list(records(source))
    source.write_text("[]\n")
    with pytest.raises(ValueError, match="JSON objects"):
        list(records(source))
    source.write_bytes(content.replace(b'"nodeId": "c-1"', b'"nodeId": ""'))
    with pytest.raises(ValueError):
        list(records(source))


def test_transactional_enterprise_import_and_prediction_binding():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for enterprise import transactions")

    async def exercise():
        schema = "test_enterprises_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                for model in (
                    User,
                    Dataset,
                    Run,
                    ModelVersion,
                    EnterpriseImport,
                    EnterpriseRecord,
                    EnterprisePrediction,
                ):
                    await connection.run_sync(model.__table__.create)
            owner, other = str(uuid4()), str(uuid4())
            source_sha = "a" * 64
            contract, content = artifact_content(source_sha)
            storage = Storage(content)
            async with sessions() as session:
                session.add(
                    User(id=owner, username="owner", password_hash="hash", display_name="O")
                )
                await session.commit()

                async def dataset(data):
                    identity = str(uuid4())
                    source = Dataset(
                        id=identity,
                        owner_id=owner,
                        name="test",
                        filename="data.zip",
                        object_key="uploads/" + identity,
                        content_type="application/zip",
                        size=123,
                        confirmed=True,
                        execution={
                            "status": "completed",
                            "result": {
                                "datasetContract": contract,
                                "sha256": source_sha,
                                "enterpriseData": {
                                    "counts": {
                                        "company": 1,
                                        "person": 2,
                                        "edge": 1,
                                        "event": 1,
                                        "hyperedge": 1,
                                    }
                                },
                                "enterpriseArtifact": {
                                    "format": FORMAT,
                                    "kind": "file",
                                    "size": len(data),
                                    "objectKey": "artifact",
                                    "sha256": hashlib.sha256(data).hexdigest(),
                                },
                            },
                        },
                    )
                    session.add(source)
                    await session.commit()
                    return source

                source = await dataset(content)
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(storage), Remote()
                )
                service = EnterpriseService(modeling)
                imported = await service.import_dataset(owner, source.id)
                assert imported.counts["company"] == 1
                again = await service.import_dataset(owner, source.id)
                assert again.sha256 == imported.sha256 and storage.reads == 1
                page = await service.page(owner, source.id, "person", "", None, None, None, 1, 1)
                assert page["total"] == 2 and len(page["items"]) == 1
                rows = await service.page(owner, source.id, "edge", "", "c-1", "train", None, 1, 20)
                assert rows["total"] == 1
                rows = await service.page(owner, source.id, "edge", "", "c-1", "test", None, 1, 20)
                assert rows["total"] == 0
                identity = source.id
                with pytest.raises(AppError) as denied:
                    await service.page(other, source.id, "company", "", None, None, None, 1, 20)
                assert denied.value.status == 404
                await session.rollback()
                run_id, model_id = str(uuid4()), str(uuid4())
                session.add(
                    Run(
                        id=run_id,
                        owner_id=owner,
                        dataset_id=identity,
                        name="R",
                        request_key=str(uuid4()),
                        configuration={},
                    )
                )
                await session.flush()
                session.add(
                    ModelVersion(id=model_id, owner_id=owner, run_id=run_id, name="M", artifact={})
                )
                await session.commit()
                await modeling.predict(owner, model_id, ["c-1"], "test")
                await modeling.predict(owner, model_id, ["c-1"], "again")
                assert (
                    await session.scalar(select(func.count()).select_from(EnterprisePrediction))
                    == 1
                )
                rows = await service.page(
                    owner, identity, "company", "", None, None, model_id, 1, 20
                )
                assert rows["items"][0]["prediction"]["probability"] == 0.25
                assert rows["items"][0]["data"]["attributes"]["revenue"] is None
                second = await dataset(content)
                await service.import_dataset(owner, second.id)
                with pytest.raises(AppError) as mismatch:
                    await service.page(owner, second.id, "company", "", None, None, model_id, 1, 20)
                assert mismatch.value.status == 409
                _, bad_content = artifact_content(source_sha, dangling=True)
                broken = await dataset(bad_content)
                storage.content = bad_content
                broken_id = broken.id
                with pytest.raises(AppError) as bad:
                    await service.import_dataset(owner, broken_id)
                assert bad.value.code == "MODELING_ENTERPRISE_INVALID"
                assert await session.get(EnterpriseImport, broken_id) is None
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(EnterpriseRecord)
                        .where(EnterpriseRecord.dataset_id == broken_id)
                    )
                    == 0
                )
                corrupted = await dataset(content)
                storage.content = content[:-1] + b"x"
                with pytest.raises(AppError) as corrupt:
                    await service.import_dataset(owner, corrupted.id)
                assert corrupt.value.code == "MODELING_ENTERPRISE_INVALID"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
