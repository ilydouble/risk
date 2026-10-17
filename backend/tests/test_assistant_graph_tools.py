import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI

from risk_api.errors import AppError
from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.projector import ItemProjector
from risk_api.modules.assistant.protocol.graph import CompanyGraphReference
from risk_api.modules.assistant.protocol.items import ToolItem
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.tools import company_tools
from risk_api.modules.assistant.tools.company_tools import CompanyGraphTools


@pytest.fixture
def tools_backend(monkeypatch):
    state = SimpleNamespace(opened=0, closed=0, graph_calls=[], unavailable=False)

    @asynccontextmanager
    async def sessions():
        state.opened += 1
        try:
            yield object()
        finally:
            state.closed += 1

    company = SimpleNamespace(id="C-1001", name_cn="北辰精密", name_en="Beichen", reg_no="REG-1")

    class Companies:
        def __init__(self, repository):
            pass

        async def search(self, query):
            assert query.page_size == 10
            return ([company], 1) if query.keyword == "北辰" else ([], 0)

        async def get_model(self, company_id):
            if company_id != company.id:
                raise AppError(404, "COMPANY_NOT_FOUND", "Company not found")
            return company

    class Graphs:
        def __init__(self, companies, repository):
            self.companies = companies

        async def get(self, company_id, lang, depth):
            await self.companies.get_model(company_id)
            if state.unavailable:
                raise RuntimeError("private connection detail")
            state.graph_calls.append((company_id, lang, depth))
            return {"nodes": [{"id": company_id}], "edges": []}

    monkeypatch.setattr(company_tools, "CompanyService", Companies)
    monkeypatch.setattr(company_tools, "GraphService", Graphs)
    return CompanyGraphTools(sessions, object()), state


def test_tool_contract_and_errors(tools_backend):
    backend, state = tools_backend

    async def exercise():
        search, show = backend.build("en")
        spec = show.tool_spec["inputSchema"]["json"]
        assert set(spec["properties"]) == {"company_id", "depth"}
        assert spec["properties"]["depth"]["minimum"] == 1
        assert spec["properties"]["depth"]["maximum"] == 3
        found = await search(keyword="北辰")
        assert found["content"][0]["json"]["companies"][0]["name"] == "Beichen"
        empty = await search(keyword="missing")
        assert empty["content"][0]["json"]["total"] == 0
        assert (await search(keyword=" "))["status"] == "error"
        assert (await show(company_id="C-1001", depth=0))["status"] == "error"
        assert (await show(company_id="C-1001", depth=4))["status"] == "error"
        missing = await show(company_id="missing")
        assert missing["content"][0]["json"]["code"] == "COMPANY_NOT_FOUND"
        result = await show(company_id="C-1001")
        reference = CompanyGraphReference.model_validate(result["content"][0]["json"])
        assert reference.depth == 2 and reference.title == "Beichen" and reference.demo
        assert state.graph_calls[-1] == ("C-1001", "en", 2)
        assert "nodes" not in result["content"][0]["json"]
        state.unavailable = True
        unavailable = await show(company_id="C-1001")
        assert unavailable["status"] == "error"
        assert "private" not in json.dumps(unavailable)
        assert state.opened == state.closed

    asyncio.run(exercise())


def test_real_sdk_search_then_graph_projection(monkeypatch, tools_backend):
    backend, state = tools_backend
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        count = len(requests)
        if count <= 2:
            name = "search_companies" if count == 1 else "show_company_graph"
            args = {"keyword": "北辰"} if count == 1 else {"company_id": "C-1001", "depth": 2}
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": f"call-{count}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ]
            }
            reason = "tool_calls"
        else:
            assert any(m.get("role") == "tool" for m in payload["messages"])
            assert "company_graph" in json.dumps(payload["messages"])
            delta, reason = {"content": "演示图谱已准备好。"}, "stop"
        chunks = [
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": {}, "finish_reason": reason}],
            },
        ]
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            text="".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n",
        )

    async def exercise():
        client = AsyncOpenAI(
            api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **kwargs: client)
        items = {}
        async for batch in StrandsRuntime(backend.sessions, company_tools=backend).stream(
            "展示北辰图谱",
            [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "key"),
            "r",
            "owner",
        ):
            for item in batch:
                items[item.id] = item
        names = {t["function"]["name"] for t in requests[0]["tools"]}
        assert {"current_time", "search_companies", "show_company_graph"} <= names
        graph_item = next(i for i in items.values() if i.kind == "tool_call" and i.graph)
        assert graph_item.status == "completed"
        assert graph_item.graph.companyId == "C-1001"
        assert graph_item.graph.summary.nodeCount == 1
        restored = ToolItem.model_validate_json(graph_item.model_dump_json())
        assert restored.graph == graph_item.graph
        assert len(requests) == 3 and state.opened == state.closed == 2

    asyncio.run(exercise())


def test_graph_card_requires_valid_successful_graph_tool_result():
    reference = {
        "kind": "company_graph",
        "companyId": "C-1001",
        "depth": 2,
        "lang": "zh",
        "title": "Demo",
        "summary": {"nodeCount": 1, "edgeCount": 0},
        "demo": True,
    }
    for name, status, data in [
        ("current_time", "success", reference),
        ("show_company_graph", "error", reference),
        ("show_company_graph", "success", {**reference, "depth": 99}),
    ]:
        projector = ItemProjector()
        projector.project({"current_tool_use": {"toolUseId": "call", "name": name, "input": "{}"}})
        result = projector.project(
            {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "call",
                                "status": status,
                                "content": [{"json": data}],
                            }
                        }
                    ],
                }
            }
        )
        assert result[-1].graph is None
