"""Uploads must reach overview/search without a workbench polling them."""

import asyncio
import hashlib
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_enterprise_data import Remote, Storage, artifact_content

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.enterprise_sync import synchronize
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


class ValidationRemote(Remote):
    def __init__(self):
        self.snapshots = {}

    async def call(self, action, body, request_id=""):
        if action == "jobs/get":
            return self.snapshots[body["jobId"]]
        return await super().call(action, body, request_id)


def test_automatic_import_overview_search_company_and_prediction_isolation():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for enterprise browsing")

    async def exercise():
        schema = "test_browse_" + uuid4().hex
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
            storage, remote = Storage(content), ValidationRemote()
            async with sessions() as session:
                session.add_all(
                    [
                        User(id=value, username=value, password_hash="hash", display_name="T")
                        for value in [owner, other]
                    ]
                )
                await session.commit()
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(storage), remote
                )
                browsing = EnterpriseBrowseService(modeling)

                async def upload(user, data, *, missing_artifact=False):
                    identity = str(uuid4())
                    dataset = Dataset(
                        id=identity,
                        owner_id=user,
                        name="上传企业数据",
                        filename="data.zip",
                        object_key=identity,
                        content_type="application/zip",
                        size=len(data),
                        confirmed=True,
                        execution={},
                    )
                    session.add(dataset)
                    await session.commit()
                    artifact = {
                        "kind": "file",
                        "format": "risk-enterprise-data-v1",
                        "objectKey": "artifact",
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                    remote.snapshots[identity] = {
                        "status": "completed",
                        "result": {
                            "datasetContract": contract,
                            "sha256": source_sha,
                            "enterpriseArtifact": {} if missing_artifact else artifact,
                            "enterpriseData": {
                                "counts": {
                                    "company": 1,
                                    "person": 2,
                                    "edge": 1,
                                    "event": 1,
                                    "hyperedge": 1,
                                }
                            },
                        },
                    }
                    return dataset

                dataset = await upload(owner, content)
                foreign = await upload(other, content)
                before = await browsing.overview(owner, dataset.id)
                assert before["dataset"]["importStatus"] == "pending"
                assert before["companies"] == []
                # No HTTP polling: the synchronizer refreshes validation itself.
                await synchronize(modeling, dataset)
                sources = await browsing.sources(owner, 1, 100)
                assert sources["total"] == 1
                assert sources["items"][0]["id"] == dataset.id
                assert sources["items"][0]["importStatus"] == "ready"
                overview = await browsing.overview(owner, dataset.id)
                assert overview["dataset"]["counts"]["company"] == 1
                assert overview["labels"] == {"positive": 1, "negative": 0, "unlabeled": 0}
                assert overview["companies"][0]["nodeId"] == "c-1"
                search = await EnterpriseService(modeling).page(
                    owner, dataset.id, "company", "c-1", None, None, None, 1, 20
                )
                assert search["total"] == 1
                profile = await browsing.company(owner, dataset.id, "c-1", None)
                assert profile["related"]["edge"]["total"] == 1
                assert profile["related"]["event"]["total"] == 1
                assert profile["related"]["hyperedge"]["total"] == 1
                with pytest.raises(AppError) as error:
                    await browsing.overview(other, dataset.id)
                assert error.value.status == 404
                with pytest.raises(AppError) as error:
                    await browsing.company(owner, dataset.id, "missing", None)
                assert error.value.code == "MODELING_COMPANY_NOT_FOUND"
                assert not await session.get(EnterpriseImport, foreign.id)

                run_id, model_id = str(uuid4()), str(uuid4())
                session.add(
                    Run(
                        id=run_id,
                        owner_id=owner,
                        dataset_id=dataset.id,
                        name="训练",
                        request_key=run_id,
                        configuration={},
                        execution={"status": "completed"},
                    )
                )
                await session.flush()
                session.add(
                    ModelVersion(
                        id=model_id, owner_id=owner, run_id=run_id, name="RiskGNN+", artifact={}
                    )
                )
                await session.commit()
                await modeling.predict(owner, model_id, ["c-1"], "test")
                overview = await browsing.overview(owner, dataset.id)
                assert overview["models"][0]["predictionCount"] == 1
                assert overview["models"][0]["positiveCount"] == 0
                assert overview["models"][0]["averageProbability"] == 0.25
                profile = await browsing.company(owner, dataset.id, "c-1", model_id)
                assert profile["company"]["prediction"]["probability"] == 0.25
                assert profile["predictions"][0]["modelId"] == model_id
                await synchronize(modeling, dataset)
                assert storage.reads == 1

                second_content = content.replace(b'"label": 1', b'"label": 0')
                second = await upload(owner, second_content)
                storage.content = second_content
                await synchronize(modeling, second)
                second_overview = await browsing.overview(owner, second.id)
                assert second_overview["labels"]["negative"] == 1
                assert second_overview["labels"]["positive"] == 0
                assert (await browsing.overview(owner, dataset.id))["labels"]["positive"] == 1
                assert (await browsing.company(owner, second.id, "c-1", None))["predictions"] == []
                with pytest.raises(AppError) as error:
                    await browsing.company(owner, second.id, "c-1", model_id)
                assert error.value.code == "MODELING_STATE_INVALID"

                _, malformed = artifact_content(source_sha, dangling=True)
                invalid = await upload(owner, malformed)
                storage.content = malformed
                invalid_id = invalid.id
                await synchronize(modeling, invalid)
                assert await session.get(EnterpriseImport, invalid_id) is None
                failed = await browsing.overview(owner, invalid_id)
                assert failed["dataset"]["importStatus"] == "failed"
                assert failed["dataset"]["importError"] == "MODELING_ENTERPRISE_INVALID"
                assert failed["companies"] == []
                assert not list(
                    await session.scalars(
                        select(EnterpriseRecord).where(EnterpriseRecord.dataset_id == invalid_id)
                    )
                )
                reads = storage.reads
                invalid = await session.get(Dataset, invalid_id)
                await synchronize(modeling, invalid)
                assert storage.reads == reads  # Failed imports honor retry backoff.
                legacy = await upload(owner, content, missing_artifact=True)
                await synchronize(modeling, legacy)
                assert (await browsing.overview(owner, legacy.id))["dataset"][
                    "importStatus"
                ] == "unavailable"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
