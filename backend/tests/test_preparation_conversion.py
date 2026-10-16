import asyncio
import csv
import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.assistant.assets import AssetRepository
from risk_api.modules.auth.model import User
from risk_api.modules.data_prep.api.schemas import RequestImportConversion, ResponseConversionState
from risk_api.modules.data_prep.conversion import ConversionPlan, execute
from risk_api.modules.data_prep.conversion_service import ConversionService
from risk_api.modules.data_prep.model import Preparation, PreparationConversion
from risk_api.modules.data_prep.repository import PreparationRepository
from risk_api.modules.data_prep.service import PreparationService
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
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

SOURCE = b"id,value,status\n001,10,active\n002,,distress\n001,10,active\n"
RULES = {
    "deduplicate": "exact",
    "labelMeaning": "0=active;1=distress; snapshot not prediction",
    "columns": [
        {"field": "id", "target": "enterprise.id", "type": "text"},
        {"field": "value", "target": "features.value", "type": "number", "missing": "null"},
        {
            "field": "status",
            "target": "enterprise.label",
            "type": "label",
            "values": {"active": 0, "distress": 1},
        },
    ],
}


def test_fixed_rules_preserve_identity_and_account_for_every_row():
    output, report = execute(SOURCE, ConversionPlan.model_validate(RULES))
    assert [r["nodeId"] for r in output] == ["001", "002"]
    assert output[1]["data"]["features"]["value"] is None
    assert output[1]["data"]["label"] == 1
    assert report["passed"] and report["inputCount"] == 3
    assert report["outputCount"] == 2 and report["duplicateCount"] == 1
    assert report["rejectedCount"] == 0


@pytest.mark.parametrize(
    "source,expected",
    [
        (b"id,value,status\n001,10,active\n001,20,active\n", "企业标识重复"),
        (b"id,value,status\n,10,active\n", "缺失值"),
        (b"id,value,status\n001,inf,active\n", "有限数值"),
        (b"id,value,status\n001,10,unknown\n", "标签值"),
    ],
)
def test_invalid_rows_block_the_entire_import(source, expected):
    _, report = execute(source, ConversionPlan.model_validate(RULES))
    assert not report["passed"] and report["rejectedCount"] == 1
    assert expected in report["issues"][0]["message"]
    assert report["inputCount"] == (
        report["outputCount"] + report["duplicateCount"] + report["rejectedCount"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "identity_number",
        "identity_null",
        "target",
        "duplicate",
        "label_meaning",
        "label_map",
        "code",
        "fill",
    ],
)
def test_plan_rejects_ambiguous_or_executable_input(change):
    plan = deepcopy(RULES)
    if change == "identity_number":
        plan["columns"][0]["type"] = "number"
    elif change == "identity_null":
        plan["columns"][0]["missing"] = "null"
    elif change == "target":
        plan["columns"][1]["target"] = "__import__.os"
    elif change == "duplicate":
        plan["columns"][1]["field"] = "id"
    elif change == "label_meaning":
        plan["labelMeaning"] = ""
    elif change == "label_map":
        plan["columns"][2]["values"] = {}
    elif change == "fill":
        plan["columns"][1]["missing"] = "fill"
    else:
        plan["script"] = "import os"
    with pytest.raises(ValidationError):
        ConversionPlan.model_validate(plan)


def test_import_requires_explicit_confirmation():
    with pytest.raises(ValidationError):
        RequestImportConversion(preparationId=uuid4(), taskId=uuid4(), confirm=False)


def test_demo_has_100_enterprises_after_explicit_rules():
    path = Path(__file__).resolve().parents[2] / "examples/data-prep/uk-company-profile-demo.csv"
    source = path.read_bytes()
    fields = next(csv.reader(source.decode("utf-8-sig").splitlines()))
    columns = []
    for field in fields:
        if field == "company_id":
            rule = {"field": field, "target": "enterprise.id", "type": "text"}
        elif field == "community":
            rule = {
                "field": field,
                "target": "enterprise.community",
                "type": "text",
                "missingValues": [""],
            }
        elif field == "adverse_status":
            rule = {
                "field": field,
                "target": "enterprise.label",
                "type": "label",
                "values": {"0": 0, "1": 1},
            }
        elif field == "source_split":
            rule = {"field": field, "target": "attributes.source_split", "type": "text"}
        else:
            rule = {
                "field": field,
                "target": f"features.{field}",
                "type": "number",
                "missing": "null",
            }
        columns.append(rule)
    plan = ConversionPlan.model_validate(
        {
            "columns": columns,
            "deduplicate": "exact",
            "labelMeaning": "0=Active;1=登记困境程序，非未来违约",
        }
    )
    output, report = execute(source, plan)
    assert report["passed"] and report["inputCount"] == 101
    assert report["outputCount"] == 100 and report["duplicateCount"] == 1
    assert sum(r["data"]["label"] for r in output) == 4
    assert sum(r["data"]["community"] == "未知" for r in output) == 4
    assert any(r["nodeId"] == "00197807" for r in output)
    assert sum(r["data"]["features"]["n_charges"] is None for r in output) == 1
    assert sum(r["data"]["features"]["max_span"] is None for r in output) == 1


def test_persist_trial_import_isolated_stale_atomic_and_idempotent():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for conversion persistence")

    async def run():
        schema = "conversion_test_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                for table in [
                    User.__table__,
                    Preparation.__table__,
                    Dataset.__table__,
                    Run.__table__,
                    ModelVersion.__table__,
                    EnterprisePrediction.__table__,
                    EnterpriseImport.__table__,
                    EnterpriseRecord.__table__,
                    PreparationConversion.__table__,
                ]:
                    await connection.run_sync(table.create)
            async with sessions.begin() as session:
                session.add_all(
                    [
                        User(id=u, username=u, password_hash="test", display_name=u)
                        for u in ["a", "b"]
                    ]
                )
            async with sessions() as session:
                prep = PreparationService(PreparationRepository(session))
                case = await prep.create("a", "test.csv", SOURCE)
                identity = case.id
                service = ConversionService(session)
                saved = await service.save_plan("a", identity, ConversionPlan.model_validate(RULES))
                assert saved["task"] is None and not case.confirmed
                state = await service.trial("a", identity)
                ResponseConversionState.model_validate(state)
                task_id = state["task"]["id"]
                assert state["task"]["status"] == "ready"
                assert (await service.trial("a", identity))["task"]["id"] == task_id
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 0
                broken = await prep.create(
                    "a",
                    "conflict.csv",
                    b"id,value,status\n001,10,active\n001,20,active\n",
                )
                broken_id = broken.id
                await service.save_plan("a", broken_id, ConversionPlan.model_validate(RULES))
                blocked = await service.trial("a", broken_id)
                assert blocked["task"]["status"] == "blocked"
                with pytest.raises(AppError):
                    await service.import_task("a", broken_id, blocked["task"]["id"])
                await session.rollback()
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 0
                for action in [
                    lambda: service.state("b", identity),
                    lambda: service.trial("b", identity),
                    lambda: service.import_task("b", identity, task_id),
                    lambda: service.save_plan("b", identity, ConversionPlan.model_validate(RULES)),
                ]:
                    with pytest.raises(AppError) as denied:
                        await action()
                    assert denied.value.status == 404
                    await session.rollback()
                case = await prep.repository.get("a", identity)
                mapping = deepcopy(case.mapping)
                changed = deepcopy(mapping)
                changed[1]["method"] = "user edited"
                await prep.save_mapping("a", identity, changed, False, False)
                with pytest.raises(AppError) as stale:
                    await service.import_task("a", identity, task_id)
                assert stale.value.code == "DATA_PREP_PLAN_STALE"
                await session.rollback()
                await service.save_plan("a", identity, ConversionPlan.model_validate(RULES))
                assert (await service.state("a", identity))["task"]["current"]
                await session.rollback()

            async def import_once():
                async with sessions() as session:
                    return await ConversionService(session).import_task("a", identity, task_id)

            first, second = await asyncio.gather(import_once(), import_once())
            dataset_id = first["task"]["datasetId"]
            assert dataset_id == second["task"]["datasetId"]
            async with sessions() as session:
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 1
                assert await session.scalar(select(func.count()).select_from(EnterpriseRecord)) == 2
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(Mock()), Mock()
                )
                browse = EnterpriseBrowseService(modeling)
                sources = await browse.sources("a", 1, 10)
                assert sources["items"][0]["importStatus"] == "ready"
                assert not (await browse.sources("b", 1, 10))["items"]
                asset = (await AssetRepository(session).datasets("a", dataset_id))[0]
                assert asset["kind"] == "enterprise_dataset" and asset["browseOnly"]
                assert asset["sourcePreparationId"] == identity
                overview = await browse.overview("a", dataset_id)
                assert overview["dataset"]["counts"] == {"company": 2}
                assert overview["labels"] == {"positive": 1, "negative": 1, "unlabeled": 0}
                records = await EnterpriseService(modeling).page(
                    "a",
                    dataset_id,
                    "company",
                    "001",
                    None,
                    None,
                    None,
                    1,
                    10,
                )
                assert records["total"] == 1 and records["items"][0]["nodeId"] == "001"
                assert not (await modeling.get_dataset("a", dataset_id)).execution["result"][
                    "supportedRunnerIds"
                ]
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(run())


def test_unknown_columns_report_exact_difference_without_saving():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    session = Mock()
    session.commit = AsyncMock()
    service = ConversionService(session)
    service.preparations.get = AsyncMock(
        return_value=SimpleNamespace(
            profile={"fields": [{"name": "id"}, {"name": "actual_value"}]},
        )
    )
    plan = ConversionPlan.model_validate(
        {
            "columns": [
                {"field": "id", "type": "text", "target": "enterprise.id"},
                {"field": "invented_value", "type": "number", "target": "features.value"},
            ]
        }
    )

    async def run():
        with pytest.raises(AppError) as error:
            await service.save_plan("owner", "case", plan)
        assert error.value.code == "DATA_PREP_RULE_INVALID"
        assert "actual_value" in error.value.message and "invented_value" in error.value.message
        session.commit.assert_not_awaited()

    asyncio.run(run())
