"""The actual agent advertises owner-free risk tools and preserves their computed output."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from risk_api.errors import AppError
from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.tools import enterprise_risk
from risk_api.modules.modeling.service import ModelingStorage


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("algorithm", ["RiskGNN", "RiskGNN+"])
def test_real_agent_uses_bound_risk_tool_and_surfaces_failure(monkeypatch, failure, algorithm):
    model_id, dataset_id = str(uuid4()), str(uuid4())
    calls, requests = [], []

    @asynccontextmanager
    async def sessions():
        yield object()

    class Repository:
        def __init__(self, session):
            pass

        async def version(self, owner, identity):
            calls.append((owner, identity))
            if failure:
                raise AppError(404, "MODELING_RESOURCE_NOT_FOUND", "模型不存在或无权访问")
            return SimpleNamespace(
                run_id="run", name="version", artifact={"profile": {"algorithm": algorithm}}
            )

        async def run(self, owner, identity):
            return SimpleNamespace(dataset_id=dataset_id)

    class Modeling:
        def __init__(self, repository, storage, client):
            self.repository = repository

        async def predict(self, owner, identity, ids, request_id, *, explain):
            calls.append((owner, identity, ids, explain))
            return {"items": [{"companyId": ids[0], "probability": 0.25,
                               "explanation": {"warnings": ["测试效果不足"],
                                               "features": [{"delta": -0.03}]}}]}

    class Browsing:
        def __init__(self, modeling):
            pass

        async def company(self, *args):
            return {"company": {"nodeId": "00805326"}, "provenance": {},
                    "related": {"edge": {"total": 0, "items": []}}}

    monkeypatch.setattr(enterprise_risk, "ModelingRepository", Repository)
    monkeypatch.setattr(enterprise_risk, "ModelingService", Modeling)
    monkeypatch.setattr(enterprise_risk, "EnterpriseBrowseService", Browsing)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            tools = {item["function"]["name"]: item["function"] for item in payload["tools"]}
            assert "enterprise_risk_catalog" in tools
            assert "enterprise_risk_companies" in tools
            assert not any("delete" in name for name in tools)
            assert "owner" not in json.dumps(tools["enterprise_risk_predict"]["parameters"])
            delta = {"tool_calls": [{"index": 0, "id": "risk", "type": "function",
                                    "function": {"name": "enterprise_risk_predict", "arguments":
                                        json.dumps({"model_id": model_id,
                                                    "company_id": "00805326"})}}]}
            stop = "tool_calls"
        else:
            output = next(item for item in payload["messages"] if item["role"] == "tool")
            assert ("MODELING_RESOURCE_NOT_FOUND" if failure else "测试效果不足") in str(output)
            delta, stop = {"content": "未获得结果" if failure else "计算完成，测试效果不足"}, "stop"
        chunks = [
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": {}, "finish_reason": stop}]},
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    async def exercise():
        client = AsyncOpenAI(api_key="test", http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ))
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **kwargs: client)
        items = {}
        agent = StrandsRuntime(sessions, ModelingStorage(object()), object())
        async for batch in agent.stream(
            "解释企业风险", [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "k"),
            "request", "bound-owner",
        ):
            for item in batch:
                items[item.id] = item
        tool = next(item for item in items.values() if item.kind == "tool_call")
        assert tool.status == ("failed" if failure else "completed")
    asyncio.run(exercise())
    assert calls[0] == ("bound-owner", model_id)
    if not failure:
        assert calls[1] == ("bound-owner", model_id, ["00805326"], algorithm == "RiskGNN+")
