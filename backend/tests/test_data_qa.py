"""Stable boundary: model plans cannot escape approved, owner-scoped read queries."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from risk_api.app import create_app
from risk_api.errors import AppError
from risk_api.modules.data_qa.catalog import CATALOG
from risk_api.modules.data_qa.plan import QueryPlan
from risk_api.modules.data_qa.query import compile_query
from risk_api.modules.data_qa.service import DataQAService, parse_reply


def plan(**kwargs):
    return QueryPlan.model_validate(
        {"table": "enterprises", "columns": ["company_id", "name"], **kwargs}
    )


def sql_of(query):
    return query.statement.compile(dialect=postgresql.dialect())


@pytest.mark.parametrize("name", CATALOG)
def test_every_view_scopes_sources_before_aggregation(name):
    query = compile_query(
        "owner-private",
        "dataset-private",
        "model-private",
        QueryPlan(
            table=name,
            metrics=[{"function": "count", "alias": "total"}],
        ),
    )
    sql = sql_of(query)
    assert "workbench_datasets.owner_id =" in str(sql)
    assert "owned_data.dataset_id =" in str(sql)
    assert "owner-private" not in str(sql)
    assert "owner-private" in sql.params.values()
    assert "dataset-private" in sql.params.values()
    assert str(sql).startswith("SELECT count(*)")
    if name in {"models", "predictions"}:
        assert "workbench_model_versions.owner_id =" in str(sql)
        assert "workbench_runs.owner_id =" in str(sql)
    if name == "predictions":
        assert "owned_data.model_id =" in str(sql)
        assert "model-private" in sql.params.values()


def test_filters_are_bound_and_like_metacharacters_are_escaped():
    attack = "x%' OR 1=1; DROP TABLE users; --"
    query = compile_query(
        "owner",
        None,
        None,
        plan(
            filters=[
                {
                    "field": "name",
                    "operator": "contains",
                    "value": attack,
                }
            ]
        ),
    )
    sql = sql_of(query)
    assert "DROP TABLE" not in str(sql)
    assert "ESCAPE" in str(sql)
    assert any("DROP TABLE" in str(value) for value in sql.params.values())
    assert any("/%" in str(value) for value in sql.params.values())
    assert sql.params["param_1"] == 51


@pytest.mark.parametrize(
    "value",
    [
        {"table": "users"},
        {"columns": ["password"]},
        {"columns": ["name; DROP TABLE users"]},
        {"sql": "SELECT * FROM users"},
        {"limit": 1000},
        {"groupBy": ["name"]},
        {"filters": [{"field": "owner_id", "operator": "eq", "value": "other"}]},
        {"filters": [{"field": "name", "operator": "contains", "value": ["x"]}]},
        {"filters": [{"field": "attributes", "operator": "eq", "value": "x"}]},
        {"orderBy": [{"field": "unknown"}]},
        {"columns": [], "metrics": [{"function": "avg", "field": "name", "alias": "mean"}]},
        {"columns": [], "metrics": [{"function": "count", "alias": "dataset_id"}]},
    ],
)
def test_rejects_unapproved_or_invalid_plans(value):
    with pytest.raises((ValidationError, ValueError)):
        compile_query("owner", None, None, plan(**value))


def test_prediction_grouped_counts_keep_model_identity_and_filter():
    value = QueryPlan(
        table="predictions",
        groupBy=["model_id", "model_name", "predicted_label"],
        metrics=[{"function": "count", "alias": "total"}],
        filters=[{"field": "probability", "operator": "gte", "value": 0.7}],
        orderBy=[{"field": "total", "direction": "desc"}],
        limit=10,
    )
    sql = sql_of(compile_query("owner", None, None, value))
    assert "GROUP BY owned_data.model_id, owned_data.model_name, owned_data.predicted_label" in str(
        sql
    )
    assert "owned_data.probability >=" in str(sql)
    assert 0.7 in sql.params.values()
    assert "ORDER BY total DESC NULLS LAST" in str(sql)


def test_parser_accepts_json_fence_but_rejects_model_claimed_results():
    content = json.dumps({"plan": plan().model_dump(), "reason": None})
    assert parse_reply(f"```json\n{content}\n```").plan.table == "enterprises"
    with pytest.raises(ValidationError):
        parse_reply('{"plan": null, "reason": "not supported", "rows": [{"total": 100}]}')


class Repository:
    def __init__(self, rows, scope_error=False):
        self.rows, self.calls, self.scope_error = rows, 0, scope_error

    async def check_scope(self, owner, dataset, model):
        if self.scope_error:
            raise AppError(404, "DATA_QA_SCOPE_NOT_FOUND", "No access")

    async def execute(self, query):
        self.calls += 1
        self.query = query
        return self.rows


class Chat:
    def __init__(self, replies):
        self.replies, self.calls = replies, 0

    async def complete(self, messages):
        result = self.replies[self.calls]
        self.calls += 1
        return SimpleNamespace(content=result, model="qwen")


def test_answer_uses_actual_database_count_not_model_output():
    repository = Repository([{"total": 7}])
    chat = Chat(
        [
            json.dumps(
                {
                    "plan": {
                        "table": "enterprises",
                        "metrics": [{"function": "count", "alias": "total"}],
                    }
                }
            )
        ]
    )
    answer = asyncio.run(
        DataQAService(repository, chat).ask("private-user-id", "有多少企业", None, None)
    )
    assert answer["rows"] == [{"total": 7}]
    assert answer["answer"] == "数量：7"
    assert repository.calls == chat.calls == 1
    assert "private-user-id" not in answer["sql"]


def test_empty_result_never_retries_or_weakens_filters():
    repository = Repository([])
    query = plan(filters=[{"field": "name", "operator": "eq", "value": "不存在"}])
    chat = Chat([json.dumps({"plan": query.model_dump()})])
    answer = asyncio.run(DataQAService(repository, chat).ask("owner", "查企业", None, None))
    assert answer["rows"] == []
    assert answer["plan"]["filters"][0]["value"] == "不存在"
    assert repository.calls == chat.calls == 1


def test_scope_is_checked_before_sending_question_to_model():
    repository, chat = Repository([], scope_error=True), Chat([])
    with pytest.raises(AppError) as error:
        asyncio.run(DataQAService(repository, chat).ask("owner", "问题", "other-dataset", None))
    assert error.value.code == "DATA_QA_SCOPE_NOT_FOUND"
    assert repository.calls == chat.calls == 0


def test_invalid_plan_is_repaired_once_and_result_limit_is_reported():
    repository = Repository([{"name": "a"}, {"name": "b"}])
    chat = Chat(["not json", json.dumps({"plan": plan(columns=["name"], limit=1).model_dump()})])
    answer = asyncio.run(DataQAService(repository, chat).ask("owner", "查企业名称", None, None))
    assert chat.calls == 2
    assert repository.calls == 1
    assert answer["truncated"] is True
    assert answer["rows"] == [{"name": "a"}]


def test_two_invalid_plans_do_not_execute():
    repository, chat = Repository([]), Chat(["bad", "bad"])
    with pytest.raises(AppError) as error:
        asyncio.run(DataQAService(repository, chat).ask("owner", "查企业", None, None))
    assert error.value.code == "DATA_QA_PLAN_INVALID"
    assert repository.calls == 0


def test_unsupported_question_is_not_executed():
    repository, chat = Repository([]), Chat(['{"plan":null,"reason":"当前不支持修改数据"}'])
    with pytest.raises(AppError) as error:
        asyncio.run(DataQAService(repository, chat).ask("owner", "删除数据", None, None))
    assert error.value.code == "DATA_QA_UNSUPPORTED"
    assert repository.calls == 0


def test_data_qa_routes_require_authenticated_session():
    with TestClient(create_app()) as client:
        for path, body in [("catalog", {}), ("ask", {"question": "有多少企业"})]:
            response = client.post(
                f"/api/v1/data-qa/{path}", json=body, headers={"Origin": "http://localhost:18080"}
            )
            assert response.status_code == 401
            assert set(response.json()) == {"code", "internal_code", "message", "data"}
            assert response.headers["X-Request-ID"]


def test_postgres_owner_scope_counts_and_readonly_transactions():
    import os
    from uuid import uuid4

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from risk_api.modules.auth.model import User
    from risk_api.modules.data_qa.repository import DataQARepository
    from risk_api.modules.modeling.workbench_model import (
        Dataset,
        EnterpriseImport,
        EnterprisePrediction,
        EnterpriseRecord,
        ModelVersion,
        Run,
    )

    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for PostgreSQL query isolation")

    async def exercise():
        schema = "test_data_qa_" + uuid4().hex
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
            first, second = str(uuid4()), str(uuid4())
            run_id, model_id = str(uuid4()), str(uuid4())
            async with sessions() as session:
                session.add_all(
                    [
                        User(
                            id=identity,
                            username=identity,
                            password_hash="hash",
                            display_name="Test",
                        )
                        for identity in [owner, other]
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        Dataset(
                            id=identity,
                            owner_id=user,
                            name="数据集",
                            filename="data.zip",
                            object_key=identity,
                            content_type="application/zip",
                            size=10,
                            confirmed=True,
                            execution={"status": "completed"},
                        )
                        for identity, user in [(first, owner), (second, other)]
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        EnterpriseImport(
                            dataset_id=identity, sha256="a" * 64, manifest={}, counts={"company": 1}
                        )
                        for identity in [first, second]
                    ]
                )
                session.add(
                    Run(
                        id=run_id,
                        owner_id=owner,
                        dataset_id=first,
                        name="训练",
                        request_key="key",
                        configuration={"resolvedParameters": {"algorithm": "riskgnn-plus"}},
                        execution={"status": "completed"},
                    )
                )
                await session.flush()
                session.add(
                    ModelVersion(
                        id=model_id, owner_id=owner, run_id=run_id, name="模型", artifact={}
                    )
                )
                session.add_all(
                    [
                        EnterpriseRecord(
                            dataset_id=identity,
                            sequence=1,
                            kind="company",
                            snapshot="train",
                            node_id="company-1",
                            members=[],
                            data={"name": "测试企业", "attributes": {"x": 1}, "label": 1},
                        )
                        for identity in [first, second]
                    ]
                )
                await session.flush()
                session.add(
                    EnterprisePrediction(
                        model_id=model_id,
                        company_id="company-1",
                        dataset_id=first,
                        result={"probability": 0.8, "predictedLabel": 1},
                    )
                )
                await session.commit()
                repo = DataQARepository(session)
                catalog = await repo.catalog(owner)
                assert [d["id"] for d in catalog["datasets"]] == [first]
                assert [m["id"] for m in catalog["models"]] == [model_id]
                for table in CATALOG:
                    value = QueryPlan(table=table, metrics=[{"function": "count", "alias": "n"}])
                    rows = await repo.execute(compile_query(owner, None, None, value))
                    assert rows == [{"n": 1}], table
                predictions = QueryPlan(
                    table="predictions",
                    columns=["company_id", "probability", "name"],
                    filters=[{"field": "probability", "operator": "gte", "value": 0.7}],
                )
                rows = await repo.execute(compile_query(owner, first, model_id, predictions))
                assert rows[0] == {
                    "company_id": "company-1",
                    "probability": 0.8,
                    "name": "测试企业",
                }
                with pytest.raises(AppError):
                    await repo.check_scope(other, first, model_id)
                value = QueryPlan(
                    table="enterprises", metrics=[{"function": "count", "alias": "n"}]
                )
                assert await repo.execute(compile_query(other, first, None, value)) == [{"n": 0}]
                with pytest.raises(DBAPIError):
                    async with repo.readonly():
                        await session.execute(text("DELETE FROM workbench_datasets"))
                assert await repo.execute(compile_query(owner, first, None, value)) == [{"n": 1}]

            from risk_api.modules.assistant.tools.data_qa import data_qa_tools

            class Planner:
                async def complete(self, messages):
                    from risk_api.modules.chat.service import ChatReply

                    return ChatReply(
                        json.dumps({"plan": value.model_dump(), "reason": None}), "test", 1
                    )

            catalog_tool, ask_tool = data_qa_tools(sessions, owner, Planner())
            listed = await catalog_tool()
            assert [d["id"] for d in listed["content"][0]["json"]["datasets"]] == [first]
            result = await ask_tool("企业有多少家？", dataset_id=first)
            assert result["status"] == "success"
            assert result["content"][0]["json"]["rows"] == [{"n": 1}]
            denied = await ask_tool("企业有多少家？", dataset_id=second)
            assert denied["status"] == "error"
            assert denied["content"][0]["json"]["code"] == "DATA_QA_SCOPE_NOT_FOUND"
            # Two owners share the runtime/session factory, never a mutable account context.
            _, other_ask = data_qa_tools(sessions, other, Planner())
            own_result, other_result = await asyncio.gather(
                ask_tool("企业有多少家？", dataset_id=first),
                other_ask("企业有多少家？", dataset_id=first),
            )
            assert own_result["status"] == "success"
            assert other_result["status"] == "error"
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
