import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from risk_api.errors import AppError
from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.tools import data_qa


@pytest.mark.parametrize(
    ("name", "failure", "expected_status"),
    [
        ("workbench_catalog", None, "completed"),
        ("workbench_ask", None, "completed"),
        ("workbench_ask", "scope", "failed"),
        ("workbench_ask", "upstream", "failed"),
        ("workbench_ask", "arguments", "failed"),
    ],
)
def test_real_strands_workbench_loop_binds_owner_and_returns_safe_results(
    monkeypatch, name, failure, expected_status
):
    calls, sessions, requests = [], [], []
    dataset, model = str(uuid4()), str(uuid4())
    arguments = {} if name == "workbench_catalog" else {
        "question": "  列出最高风险预测  ", "dataset_id": dataset, "model_id": model,
    }
    if failure == "arguments":
        arguments["dataset_id"] = "not-a-uuid"

    @asynccontextmanager
    async def session_factory():
        session = object()
        sessions.append(("opened", session))
        try:
            yield session
        finally:
            sessions.append(("closed", session))

    class Service:
        def __init__(self, repository, chat):
            assert repository.session is sessions[-1][1]
            assert chat.url == "http://model/v1/chat/completions"
            assert chat.model == "test" and chat.token == "private-key"
            assert not chat.require_token

        async def catalog(self, owner):
            calls.append((owner,))
            return {"datasets": [{"id": dataset, "name": "sample"}], "truncated": False}

        async def ask(self, owner, question, dataset_id, model_id):
            calls.append((owner, question, dataset_id, model_id))
            if failure == "scope":
                raise AppError(404, "DATA_QA_SCOPE_NOT_FOUND", "数据集不存在或无权访问")
            if failure == "upstream":
                raise RuntimeError("private-key upstream body")
            return {
                "rows": [{"probability": 0.8}], "warnings": ["概率不代表违约概率"],
                "truncated": True, "sql": "SELECT probability WHERE dataset_id = :dataset_id",
                "plan": {"table": "predictions"},
            }

    monkeypatch.setattr(data_qa, "DataQAService", Service)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            schemas = {t["function"]["name"]: t["function"] for t in payload["tools"]}
            assert set(schemas) == {
                "current_time", "workbench_catalog", "workbench_ask", "asset_catalog", "asset_read",
            }
            assert "owner" not in json.dumps(schemas["workbench_ask"]["parameters"])
            delta = {"tool_calls": [{
                "index": 0, "id": "query-1", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }]}
            stop = "tool_calls"
        else:
            result = next(m for m in payload["messages"] if m["role"] == "tool")
            content = json.loads(result["content"])
            assert "private-key" not in result["content"]
            if failure:
                assert content["code"] == {
                    "scope": "DATA_QA_SCOPE_NOT_FOUND", "upstream": "DATA_QA_TOOL_FAILED",
                    "arguments": "DATA_QA_ARGUMENT_INVALID",
                }[failure]
            elif name == "workbench_ask":
                assert content["rows"] == [{"probability": 0.8}]
                assert content["truncated"] and content["warnings"]
                assert "sql" in content and "plan" in content
            else:
                assert content["datasets"][0]["id"] == dataset
            delta, stop = {"content": "查询失败。" if failure else "查询完成。"}, "stop"
        chunks = [
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": {}, "finish_reason": stop}]},
        ]
        body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    async def exercise():
        client = AsyncOpenAI(
            api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **kwargs: client)
        items = {}
        async for batch in StrandsRuntime(session_factory).stream(
            "查询数据", [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "private-key"),
            "request", "authenticated-owner",
        ):
            for item in batch:
                items[item.id] = item
        tool = next(i for i in items.values() if i.kind == "tool_call")
        assert tool.status == expected_status
        assert "private-key" not in tool.model_dump_json()
        assert len(requests) == 2

    asyncio.run(exercise())
    if failure == "arguments":
        assert not calls and not sessions
    else:
        assert calls == ([("authenticated-owner",)] if name == "workbench_catalog" else [
            ("authenticated-owner", "列出最高风险预测", dataset, model),
        ])
        assert len(sessions) == 2
        assert sessions[0][0] == "opened" and sessions[1] == ("closed", sessions[0][1])
