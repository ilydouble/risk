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


@pytest.mark.parametrize("action", ["save_plan", "trial", "result", "invalid", "failure"])
def test_real_agent_preparation_tools_bind_owner_and_never_expose_import(monkeypatch, action):
    identity = str(uuid4())
    calls, requests = [], []
    name = (
        f"preparation_{action}"
        if action in {"save_plan", "trial", "result"}
        else "preparation_trial"
    )
    args = {"preparation_id": identity if action != "invalid" else "not-a-uuid"}
    if action == "save_plan":
        args["plan"] = {"columns": [{"field": "id", "target": "enterprise.id", "type": "text"}]}

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
            if action in {"failure", "invalid"}:
                assert content["code"] == (
                    "DATA_PREP_TOOL_FAILED" if action == "failure" else "DATA_PREP_RULE_INVALID"
                )
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
        assert tool.status == ("failed" if action in {"failure", "invalid"} else "completed")

    asyncio.run(run())
    assert calls == ([] if action == "invalid" else [("bound-owner", identity)])
