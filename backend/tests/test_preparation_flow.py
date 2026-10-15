import asyncio
import io
import os
import zipfile
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.data_prep.api import handler
from risk_api.modules.data_prep.api.schemas import RequestGetPreparation
from risk_api.modules.data_prep.model import Preparation
from risk_api.modules.data_prep.profile import inspect_csv
from risk_api.modules.data_prep.repository import PreparationRepository
from risk_api.modules.data_prep.service import (
    PreparationService,
    proposed_mapping,
    validate_mapping,
)
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import Dataset

SOURCE = b"company_id,age,status\n001,10,0\n002,20,1\n"
PLAN = [
    {"field": "company_id", "role": "identity", "target": "enterprise.id",
     "method": "保留文本和前导零", "reason": "企业标识"},
    {"field": "age", "role": "feature", "target": "features.age",
     "method": "数值解析，训练集拟合缺失处理", "reason": "数值特征"},
    {"field": "status", "role": "label", "target": "enterprise.label",
     "method": "0正常，1登记不良状态；不是贷款违约", "reason": "来源定义"},
]


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown", "unresolved", "target"])
def test_confirmation_requires_complete_mapping(change):
    mapping = deepcopy(PLAN)
    if change == "missing":
        mapping.pop()
    elif change == "duplicate":
        mapping[1]["field"] = mapping[0]["field"]
    elif change == "unknown":
        mapping[1]["role"] = "unknown"
    elif change == "unresolved":
        mapping[1]["method"] = "待确认"
    else:
        mapping[1]["target"] = mapping[0]["target"]
    with pytest.raises(AppError) as error:
        validate_mapping(inspect_csv(SOURCE), mapping, True)
    assert error.value.code == "DATA_PREP_MAPPING_INVALID"


def test_proposals_are_not_confirmed_mappings():
    profile = inspect_csv(SOURCE)
    proposed = proposed_mapping(profile, {"suggestions": [
        {"field": "company_id", "role": "identity", "reason": "待确认线索"},
    ]})
    assert [entry["field"] for entry in proposed] == ["company_id", "age", "status"]
    assert proposed[1]["role"] == "unknown"
    validate_mapping(profile, proposed, False)
    with pytest.raises(AppError):
        validate_mapping(profile, proposed, True)


def test_persist_restore_handoff_preserves_source_and_owner_scope():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for preparation persistence")

    async def run():
        schema = "preparation_test_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(User.__table__.create)
                await connection.run_sync(Preparation.__table__.create)
                await connection.run_sync(Dataset.__table__.create)
            async with sessions.begin() as session:
                session.add_all([User(id=u, username=u, password_hash="test", display_name=u)
                                 for u in ["a", "b"]])
            async with sessions() as session:
                service = PreparationService(PreparationRepository(session))
                case = await service.create("a", "case.csv", SOURCE)
                identity = case.id
                same = await service.create("a", "renamed.csv", SOURCE)
                assert same.id == identity and same.source == SOURCE
                await service.report("a", identity, {
                    "summary": "已分析", "suggestions": [], "questions": [],
                })
                with pytest.raises(AppError):
                    await service.save_mapping("a", identity, PLAN, False, True)
                await session.rollback()
                await service.save_mapping("a", identity, PLAN, True, True)
                storage = Mock()
                storage.presign_put = AsyncMock(return_value=SimpleNamespace(url="url", headers={}))
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(storage), Mock(),
                )
                with pytest.raises(AppError):
                    await modeling.create_upload(
                        "b", "derived", "data.zip", "application/zip", 10, identity,
                    )
                await session.rollback()
                ticket = await modeling.create_upload(
                    "a", "derived", "data.zip", "application/zip", 10, identity,
                )
                derived = await session.get(Dataset, ticket["datasetId"])
                assert derived.source_preparation_id == identity
                assert derived.mapping_snapshot["mapping"] == PLAN
                changed = deepcopy(PLAN)
                changed[1]["method"] = "更新后的草稿规则"
                await service.save_mapping("a", identity, changed, False, False)
                assert derived.mapping_snapshot["mapping"] == PLAN
                await service.save_mapping("a", identity, PLAN, True, True)
                await service.report("a", identity, {
                    "summary": "新报告", "suggestions": [], "questions": [],
                })
            async with sessions() as session:
                repository = PreparationRepository(session)
                restored = await repository.get("a", identity)
                assert restored.source == SOURCE and restored.profile["rowCount"] == 2
                assert restored.confirmed and restored.in_workbench and restored.mapping == PLAN
                assert restored.report["summary"] == "新报告"
                assert len(await repository.list("a", workbench_only=True)) == 1
                assert await repository.list("b") == []
                with patch.object(handler, "authorize_request",
                                  AsyncMock(return_value={"user_id": "a"})):
                    request = Request({"type": "http"})
                    body = RequestGetPreparation(preparationId=identity)
                    restored_response = await handler.get_preparation(
                        body, request, Mock(), PreparationService(repository),
                    )
                    assert restored_response.data.profile.preparationId == identity
                    bundle = await handler.export_preparation(
                        body, request, Mock(), PreparationService(repository),
                    )
                import base64

                exported = io.BytesIO(base64.b64decode(bundle.data.contentBase64))
                with zipfile.ZipFile(exported) as archive:
                    assert archive.read("source.csv") == SOURCE
                    assert "preparation.json" in archive.namelist()
                    assert "risk_dataset_contract.json" not in archive.namelist()
                with pytest.raises(AppError) as error:
                    await repository.get("b", identity)
                assert error.value.code == "DATA_PREP_NOT_FOUND"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(run())
