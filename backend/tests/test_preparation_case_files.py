import asyncio
import hashlib
import json
import os
from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.data_prep.api.schemas import (
    RequestDeletePreparation,
    ResponseConversionState,
    ResponsePreparation,
    ResponsePreparationDeletion,
)
from risk_api.modules.data_prep.case_files import (
    CASE_ENGINE,
    build_case,
    execute_case,
    graph_document,
    primary_source,
    unpack_source,
)
from risk_api.modules.data_prep.conversion import ConversionPlan
from risk_api.modules.data_prep.conversion_service import ConversionService
from risk_api.modules.data_prep.deletion import delete_preparation, deletion_scope
from risk_api.modules.data_prep.model import Preparation, PreparationConversion
from risk_api.modules.data_prep.repository import PreparationRepository
from risk_api.modules.data_prep.service import PreparationService
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
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

CSV = b"company_id,value\n001,10\n002,20\n001,10\n"
PLAN = ConversionPlan.model_validate({
    "columns": [{"field": "company_id", "target": "enterprise.id", "type": "text"},
                {"field": "value", "target": "features.value", "type": "number"}],
    "deduplicate": "exact",
})
GRAPH = {
    "nodes": [{"id": "001", "features": [10]}, {"id": "002", "features": [20]}],
    "feature_names": ["value"],
    "edges": [{"source": "001", "target": "002", "relation": "EQUITY", "weight": 1.0}],
    "hyperedges": [{"kind": "director_group", "members": ["001", "002"]}],
}


def encoded(graph):
    return json.dumps(graph).encode()


def test_case_container_is_order_independent_and_source_bytes_are_preserved():
    files = [("companies.csv", CSV), ("relations.json", encoded(GRAPH))]
    source, profile = build_case(files)
    assert build_case(list(reversed(files))) == (source, profile)
    assert dict(unpack_source(source, profile)) == dict(files)
    assert primary_source(source, profile) == ("companies.csv", CSV)
    assert profile["sha256"] == hashlib.sha256(source).hexdigest()
    assert build_case([files[0]])[0] == CSV
    output, report = execute_case(source, profile, PLAN)
    assert report["passed"]
    assert report["counts"] == {"company": 2, "edge": 1, "hyperedge": 1}
    assert report["duplicateCount"] == 1 and report["outputCount"] == 4
    assert report["graph"]["matchedCount"] == 2 and report["graph"]["missingCount"] == 0
    assert output[0]["nodeId"] == "001"
    assert output[2]["source"] == "001" and output[3]["members"] == ["001", "002"]
    assert output[2]["data"]["sourceRecord"] == {
        "filename": "relations.json", "sha256": hashlib.sha256(encoded(GRAPH)).hexdigest(),
        "path": "edges[0]",
    }


@pytest.mark.parametrize("change", ["endpoint", "node", "property", "feature_count", "weight"])
def test_missing_nodes_and_conflicts_block_case_without_silent_overwrite(change):
    graph = deepcopy(GRAPH)
    extra = []
    if change == "endpoint":
        graph["edges"][0]["target"] = "003"
    elif change == "node":
        graph["nodes"].append({"id": "003"})
    elif change == "property":
        graph["nodes"][0]["features"] = [99]
    elif change == "feature_count":
        graph["nodes"][0]["features"] = []
    else:
        different = deepcopy(GRAPH)
        different["edges"][0]["weight"] = 0.5
        extra = [("second.json", encoded(different))]
    source, profile = build_case(
        [("companies.csv", CSV), ("relations.json", encoded(graph)), *extra]
    )
    output, report = execute_case(source, profile, PLAN)
    assert not report["passed"] and report["issueCount"] > 0
    assert report["issues"][0]["filename"].endswith(".json")
    assert report["issues"][0]["path"]
    assert output[0]["data"]["features"]["value"] == 10
    if change in {"endpoint", "node"}:
        assert report["graph"]["missingIds"] == ["003"]
    else:
        assert report["graph"]["conflictCount"] > 0


def test_graph_name_does_not_conflict_with_id_fallback_when_csv_has_no_name_rule():
    graph = deepcopy(GRAPH)
    graph["nodes"][0]["name"] = "Registered company name"
    source, profile = build_case([("companies.csv", CSV), ("graph.json", encoded(graph))])
    _, report = execute_case(source, profile, PLAN)
    assert report["passed"]


def test_invalid_graph_error_identifies_file():
    with pytest.raises(AppError) as error:
        build_case([("companies.csv", CSV), ("wrong.json", b'{"links":[]}')])
    assert "wrong.json" in error.value.message


def test_duplicate_graph_evidence_is_counted_and_imported_once():
    source, profile = build_case([("companies.csv", CSV),
                                  ("one.json", encoded(GRAPH)), ("two.json", encoded(GRAPH))])
    _, report = execute_case(source, profile, PLAN)
    assert report["passed"] and report["graph"]["duplicateCount"] == 2
    assert report["counts"] == {"company": 2, "edge": 1, "hyperedge": 1}


@pytest.mark.parametrize("content", [
    b'{"edges":[],"edges":[]}',
    b'{"edges":[{"source":1,"target":"002","relation":"EQUITY"}]}',
    b'{"edges":[{"source":"001","target":"002","relation":"EQUITY","weight":NaN}]}',
    b'{"hyperedges":[{"kind":"director_group","members":["001","001"]}]}',
    b'{"edges":[],"nodes":[{"id":"001","kind":"person"}]}',
    b'{"edges":[],"events":[{"company":"001"}]}',
    b'{"links":[]}',
])
def test_unsupported_or_ambiguous_graph_is_rejected(content):
    with pytest.raises(AppError) as error:
        graph_document(content)
    assert error.value.code == "DATA_PREP_GRAPH_INVALID"


@pytest.mark.parametrize("files", [
    [("one.csv", CSV), ("two.csv", CSV)],
    [("one.csv", CSV), ("one.csv", CSV)],
    [("../one.csv", CSV)],
    [("one.json", encoded(GRAPH))],
])
def test_case_requires_explicit_single_primary_table_and_safe_file_names(files):
    with pytest.raises(AppError):
        build_case(files)


def test_append_revision_import_graph_and_provenance_are_owner_scoped_and_atomic():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for case persistence")

    async def run():
        schema = "case_files_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                for table in [User.__table__, Preparation.__table__, Dataset.__table__,
                              Run.__table__,
                              ModelVersion.__table__, EnterprisePrediction.__table__,
                              EnterpriseImport.__table__, EnterpriseRecord.__table__,
                              PreparationConversion.__table__]:
                    await connection.run_sync(table.create)
            async with sessions.begin() as session:
                session.add_all([User(id=u, username=u, password_hash="test", display_name=u)
                                 for u in ["a", "b"]])
            async with sessions() as session:
                prep = PreparationService(PreparationRepository(session))
                original = await prep.create("a", "companies.csv", CSV)
                original_id = original.id
                await ConversionService(session).save_plan("a", original_id, PLAN)
                case = await prep.create_case("a", [("graph.json", encoded(GRAPH))], original_id)
                identity = case.id
                assert identity != original_id and not case.confirmed and not case.report
                assert case.conversion_plan["rules"] == PLAN.model_dump()
                assert (await ConversionService(session).state("a", identity))["task"] is None
                assert case.profile["previousPreparationId"] == original_id
                assert (await prep.repository.get("a", original_id)).source == CSV
                from risk_api.modules.data_prep.api.handler import preparation_response
                ResponsePreparation.model_validate(preparation_response(case))
                assert (await prep.create_case("a", [("graph.json", encoded(GRAPH))],
                                               original_id)).id == identity
                with pytest.raises(AppError) as denied:
                    await prep.create_case("b", [("graph.json", encoded(GRAPH))], original_id)
                assert denied.value.status == 404
                await session.rollback()
                service = ConversionService(session)
                await service.save_plan("a", identity, PLAN)
                state = await service.trial("a", identity)
                ResponseConversionState.model_validate(state)
                assert state["task"]["engineVersion"] == CASE_ENGINE
                task = state["task"]["id"]
                assert (await service.trial("a", identity))["task"]["id"] == task
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 0
                imported = await service.import_task("a", identity, task)
                dataset_id = imported["task"]["datasetId"]
                again = await service.import_task("a", identity, task)
                assert again["task"]["datasetId"] == dataset_id
                assert await session.scalar(select(func.count()).select_from(EnterpriseRecord)) == 4
                modeling = ModelingService(
                    ModelingRepository(session), ModelingStorage(Mock()), Mock()
                )
                detail = await EnterpriseBrowseService(modeling).company(
                    "a", dataset_id, "001", None
                )
                assert detail["provenance"]["status"] == "available"
                assert detail["provenance"]["filename"] == "companies.csv"
                assert detail["provenance"]["sourceLine"] == 2
                assert detail["related"]["edge"]["total"] == 1
                assert detail["related"]["hyperedge"]["total"] == 1
                edge_source = detail["related"]["edge"]["items"][0]["data"]["sourceRecord"]
                assert edge_source["filename"] == "graph.json"
                assert detail["dataset"]["counts"] == {"company": 2, "edge": 1, "hyperedge": 1}
                with pytest.raises(AppError) as denied:
                    await EnterpriseBrowseService(modeling).company("b", dataset_id, "001", None)
                assert denied.value.status == 404
                await session.rollback()
                invalid = deepcopy(GRAPH)
                invalid["edges"][0]["target"] = "unknown"
                bad = await prep.create_case("a", [("companies.csv", CSV),
                                                  ("bad.json", encoded(invalid))])
                bad_id = bad.id
                await service.save_plan("a", bad_id, PLAN)
                blocked = await service.trial("a", bad_id)
                assert blocked["task"]["status"] == "blocked"
                with pytest.raises(AppError):
                    await service.import_task("a", bad_id, blocked["task"]["id"])
                await session.rollback()
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 1

                await prep.report("a", identity, {
                    "summary": "stored report", "suggestions": [], "questions": [],
                })
                scope = await deletion_scope(session, "a", identity)
                ResponsePreparationDeletion.model_validate(scope)
                assert scope["counts"] == {
                    "files": 2, "reports": 1, "tasks": 1, "datasets": 1, "predictions": 0,
                    "records": {"company": 2, "edge": 1, "hyperedge": 1},
                }
                with pytest.raises(AppError) as denied:
                    await delete_preparation(session, "b", identity, scope["revision"])
                assert denied.value.status == 404
                await session.rollback()
                await service.save_plan("a", identity, PLAN)
                with pytest.raises(AppError) as stale:
                    await delete_preparation(session, "a", identity, scope["revision"])
                assert stale.value.code == "DATA_PREP_DELETE_STALE"
                await session.rollback()
                run_id = str(uuid4())
                session.add(Run(id=run_id, owner_id="a", dataset_id=dataset_id, name="dependency",
                                request_key=str(uuid4()), configuration={}, execution={}))
                await session.commit()
                blocked_scope = await deletion_scope(session, "a", identity)
                assert blocked_scope["blockedReason"]
                with pytest.raises(AppError) as blocked_delete:
                    await delete_preparation(session, "a", identity, blocked_scope["revision"])
                assert blocked_delete.value.code == "DATA_PREP_DELETE_BLOCKED"
                await session.rollback()
                assert await session.scalar(select(func.count()).select_from(Dataset)) == 1
                await session.execute(delete(Run).where(Run.id == run_id))
                await session.commit()
                child = await prep.create_case("a", [("extra.json", b'{"edges":[]}')], identity)
                child_id = child.id
                assert (await deletion_scope(session, "a", identity))["blockedReason"]
                child_scope = await deletion_scope(session, "a", child_id)
                await delete_preparation(session, "a", child_id, child_scope["revision"])
                final_scope = await deletion_scope(session, "a", identity)
                deleted = await delete_preparation(session, "a", identity, final_scope["revision"])
                assert deleted["deleted"] and deleted["counts"]["reports"] == 1
                assert await session.get(Preparation, identity) is None
                assert await session.get(Dataset, dataset_id) is None
                assert await session.scalar(select(func.count()).select_from(EnterpriseRecord)) == 0
                assert (await prep.repository.get("a", original_id)).source == CSV
                assert (await service.state("a", bad_id))["task"]["status"] == "blocked"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(run())


@pytest.mark.parametrize("values", [
    {"confirm": False, "revision": "0" * 64},
    {"confirm": True},
])
def test_case_deletion_requires_explicit_confirmation_and_preview_revision(values):
    with pytest.raises(ValidationError):
        RequestDeletePreparation.model_validate({"preparationId": str(uuid4()), **values})
