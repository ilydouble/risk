import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.tools import preparation


@pytest.mark.parametrize(
    "action",
    [
        "save_plan",
        "trial",
        "result",
        "invalid",
        "failure",
        "invalid_plan",
        "invalid_label",
        "save_only",
    ],
)
def test_real_agent_preparation_tools_bind_owner_and_never_expose_import(monkeypatch, action):
    identity = str(uuid4())
    calls, requests = [], []
    name = (
        f"preparation_{action}"
        if action in {"save_plan", "trial", "result"}
        else "preparation_trial"
    )
    args = {"preparation_id": identity if action != "invalid" else "not-a-uuid"}
    if action in {"save_plan", "invalid_plan", "invalid_label", "save_only"}:
        name = "preparation_save_plan"
        args["plan"] = {"columns": [{"field": "id", "target": "enterprise.id", "type": "text"}]}
        if action == "save_only":
            args["run_trial"] = False
        if action == "invalid_label":
            args["plan"] = {
                "columns": [
                    {"field": "id", "target": "enterprise.id", "type": "text"},
                    {"field": "community", "target": "features.community", "type": "label"},
                    {
                        "field": "status",
                        "target": "enterprise.label",
                        "type": "label",
                        "values": {"0": "0", "1": "1"},
                    },
                ],
                "labelMeaning": "snapshot status",
            }
        if action == "invalid_plan":
            args["plan"] = {"columns": {"id": {}}, "labelMeaning": {"status": "unknown"}}

    @asynccontextmanager
    async def sessions():
        yield object()

    class Service:
        def __init__(self, session):
            pass

        async def save_plan(self, owner, case, plan):
            calls.append((owner, case))
            assert plan.columns[0].target == "enterprise.id"
            return {"preparationId": case, "planCurrent": True, "task": None}

        async def trial(self, owner, case):
            calls.append((owner, case))
            if action == "failure":
                raise RuntimeError("secret-key private traceback")
            return {"preparationId": case, "task": {"status": "ready", "datasetId": None}}

        async def state(self, owner, case, task):
            calls.append((owner, case))
            return {"preparationId": case, "task": {"status": "blocked", "datasetId": None}}

    monkeypatch.setattr(preparation, "ConversionService", Service)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            schemas = {tool["function"]["name"]: tool["function"] for tool in payload["tools"]}
            assert not any("import" in tool for tool in schemas)
            assert "owner" not in json.dumps(schemas[name]["parameters"])
            advertised = schemas["preparation_save_plan"]["parameters"]
            plan_schema = advertised["$defs"]["ConversionPlan"]["properties"]
            assert advertised["properties"]["run_trial"]["default"] is True
            assert plan_schema["columns"]["type"] == "array"
            assert plan_schema["labelMeaning"]["type"] == "string"
            column_schema = advertised["$defs"]["ConversionColumn"]["properties"]
            assert column_schema["values"]["additionalProperties"]["enum"] == [0, 1]
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "t",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ]
            }
            stop = "tool_calls"
        else:
            message = next(m for m in payload["messages"] if m["role"] == "tool")
            content = json.loads(message["content"])
            assert "secret-key" not in message["content"]
            if action in {"failure", "invalid", "invalid_plan", "invalid_label"}:
                assert content["code"] == (
                    "DATA_PREP_TOOL_FAILED" if action == "failure" else "DATA_PREP_RULE_INVALID"
                )
                if action == "invalid_label":
                    assert {e["path"] for e in content["errors"]} == {
                        "plan.columns.1",
                        "plan.columns.2.values.0",
                        "plan.columns.2.values.1",
                    }
                if action == "invalid_plan":
                    assert {e["path"] for e in content["errors"]} == {
                        "plan.columns",
                        "plan.labelMeaning",
                    }
                    assert "input" not in json.dumps(content["errors"])
            else:
                assert content["preparationId"] == identity
                if content["task"]:
                    assert content["task"]["datasetId"] is None
            delta, stop = {"content": "请核对卡片中的结果。"}, "stop"
        chunks = [
            {
                "id": "c",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            {
                "id": "c",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": {}, "finish_reason": stop}],
            },
        ]
        body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    async def run():
        client = AsyncOpenAI(
            api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **kwargs: client)
        items = {}
        async for batch in StrandsRuntime(sessions).stream(
            "转换案例",
            [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "key"),
            "request",
            "bound-owner",
        ):
            for item in batch:
                items[item.id] = item
        tool = next(item for item in items.values() if item.kind == "tool_call")
        assert tool.status == (
            "failed"
            if action in {"failure", "invalid", "invalid_plan", "invalid_label"}
            else "completed"
        )

    asyncio.run(run())
    expected = (
        []
        if action in {"invalid", "invalid_plan", "invalid_label"}
        else [("bound-owner", identity)] * (2 if action == "save_plan" else 1)
    )
    assert calls == expected


def test_execution_limit_is_actionable_and_agent_stream_closes_in_same_context(monkeypatch):
    from contextvars import ContextVar
    from types import SimpleNamespace

    from risk_api.errors import AppError

    context = ContextVar("test_agent_context", default="outside")
    closed = []

    class LimitedAgent:
        def __init__(self, **kwargs):
            pass

        async def stream_async(self, *args, **kwargs):
            token = context.set("inside")
            try:
                yield {"result": SimpleNamespace(stop_reason="limit_turns")}
            finally:
                context.reset(token)
                closed.append(True)

    monkeypatch.setattr(runtime, "Agent", LimitedAgent)

    async def run():
        with pytest.raises(AppError) as failure:
            async for _ in StrandsRuntime(None).stream(
                "test",
                [],
                ModelSettings("http://model/v1/chat/completions", "test", 1024, ""),
                "request",
                "owner",
            ):
                pass
        assert failure.value.code == "ASSISTANT_EXECUTION_LIMIT"
        assert context.get() == "outside" and closed == [True]

    asyncio.run(run())
