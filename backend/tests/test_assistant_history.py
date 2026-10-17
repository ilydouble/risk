"""Stable replay contracts: ordered tools, bounded history and multi-turn ID continuity."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from risk_api.modules.assistant import history, runtime
from risk_api.modules.assistant.protocol.items import AgentMessageItem, ToolItem, UserMessageItem
from risk_api.modules.assistant.protocol.turns import Turn
from risk_api.modules.assistant.tools import enterprise_risk
from risk_api.modules.modeling.service import ModelingStorage


def turn(items, **changes):
    return Turn(
        id=str(uuid4()),
        conversationId="conversation",
        status="completed",
        model="test",
        requestId="request",
        sequence=1,
        createdAt=datetime.now(UTC),
        items=items,
        **changes,
    )


def tool(**changes):
    return ToolItem(
        **{
            "toolCallId": "provider-reuses-this-id",
            "name": "enterprise_risk_catalog",
            "argumentsText": "{}",
            "result": [{"json": {"models": [{"modelId": "authoritative"}]}}],
            "status": "completed",
            **changes,
        }
    )


def test_replay_preserves_order_errors_and_unique_call_pairs():
    turns = [
        turn(
            [
                UserMessageItem(text="列模型"),
                AgentMessageItem(text="查询中"),
                tool(),
                AgentMessageItem(text="请选择模型"),
            ]
        ),
        turn(
            [
                UserMessageItem(text="再查询"),
                tool(status="failed"),
                AgentMessageItem(text="工具失败"),
            ]
        ),
    ]
    messages = history.conversation_messages(turns)
    assert [m["role"] for m in messages] == [
        "user",
        "assistant",
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    calls = [b["toolUse"] for m in messages for b in m["content"] if "toolUse" in b]
    results = [b["toolResult"] for m in messages for b in m["content"] if "toolResult" in b]
    assert len({call["toolUseId"] for call in calls}) == 2
    assert [c["toolUseId"] for c in calls] == [r["toolUseId"] for r in results]
    assert [r["status"] for r in results] == ["success", "error"]
    assert results[0]["content"] == turns[0].items[2].result


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "running"},
        {"status": "cancelled"},
        {"result": None},
        {"argumentsText": "{"},
        {"argumentsText": "[]"},
    ],
)
def test_incomplete_or_invalid_tool_pairs_are_not_replayed(changes):
    messages = history.conversation_messages(
        [
            turn(
                [
                    UserMessageItem(text="user"),
                    tool(**changes),
                    AgentMessageItem(text="answer"),
                ]
            )
        ]
    )
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_budget_counts_results_and_retains_whole_turns(monkeypatch):
    recent = turn([UserMessageItem(text="选择"), tool(), AgentMessageItem(text="继续")])
    size = len(
        json.dumps(
            history.conversation_messages([recent]), ensure_ascii=False, separators=(",", ":")
        )
    )
    monkeypatch.setattr(history, "HISTORY_CHAR_LIMIT", size)
    older = turn([UserMessageItem(text="旧"), AgentMessageItem(text="旧答案")])
    assert history.conversation_messages([older, recent]) == history.conversation_messages([recent])
    monkeypatch.setattr(history, "HISTORY_CHAR_LIMIT", size - 1)
    assert history.conversation_messages([recent]) == []
    monkeypatch.setattr(history, "HISTORY_CHAR_LIMIT", 32000)
    many = [turn([UserMessageItem(text=str(i)), AgentMessageItem(text="答")]) for i in range(12)]
    assert len(history.conversation_messages(many)) == 20
    many[-1].status = "running"
    assert history.conversation_messages(many)[-2]["content"] == [{"text": "10"}]


def test_real_strands_second_turn_receives_persisted_catalog_and_queries_exact_id(monkeypatch):
    model_id = str(uuid4())
    requests, searched = [], []

    @asynccontextmanager
    async def sessions():
        yield object()

    class Catalog:
        def __init__(self, modeling):
            pass

        async def list(self, owner, dataset_id, limit, exact):
            assert owner == "owner"
            return {"models": [{"modelId": model_id, "name": "selected-model"}]}

        async def companies(self, owner, identity, keyword, page):
            searched.append((owner, identity))
            return {"items": [{"companyId": "C00010"}]}

    monkeypatch.setattr(enterprise_risk, "ModelCatalogService", Catalog)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        index = len(requests)
        if index == 1:
            name, arguments = "enterprise_risk_catalog", {}
        elif index == 3:
            # The previous prose intentionally lacks the UUID; only replayed tool data has it.
            result = next(m for m in payload["messages"] if m["role"] == "tool")
            restored = json.loads(result["content"])
            assert restored["models"][0]["modelId"] == model_id
            call = next(m for m in payload["messages"] if m.get("tool_calls"))["tool_calls"][0]
            assert call["id"] == result["tool_call_id"]
            name, arguments = (
                "enterprise_risk_companies",
                {"model_id": restored["models"][0]["modelId"]},
            )
        if index in (1, 3):
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "reused",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ]
            }
            stop = "tool_calls"
        else:
            delta = {"content": "请选择 selected-model" if index == 2 else "企业 C00010"}
            stop = "stop"
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
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            text="".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n",
        )

    def model_client(**kwargs):
        return AsyncOpenAI(
            api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )

    monkeypatch.setattr(runtime, "AsyncOpenAI", model_client)

    async def exercise():
        agent = runtime.StrandsRuntime(sessions, ModelingStorage(object()), object())
        settings = runtime.ModelSettings("http://model/v1/chat/completions", "test", 1024, "k")
        first = UserMessageItem(text="列出模型", status="completed")
        items = {first.id: first}
        async for batch in agent.stream(first.text, [], settings, "r1", "owner"):
            for item in batch:
                items[item.id] = item
        saved = Turn.model_validate_json(turn(list(items.values())).model_dump_json())
        async for _ in agent.stream("我选择 selected-model", [saved], settings, "r2", "owner"):
            pass

    asyncio.run(exercise())
    assert len(requests) == 4
    assert searched == [("owner", model_id)]


@pytest.mark.parametrize(
    ("name", "arguments", "field"),
    [
        ("enterprise_risk_catalog", {"model_id": "model-name"}, "model_id"),
        ("enterprise_risk_catalog", {"dataset_id": "dataset-name"}, "dataset_id"),
        ("enterprise_risk_catalog", {"limit": 0}, "limit"),
        ("enterprise_risk_companies", {"model_id": "model-name"}, "model_id"),
        ("enterprise_risk_predict", {"model_id": "model-name", "company_id": "C1"}, "model_id"),
    ],
)
def test_parameter_errors_identify_field_and_explain_recovery(name, arguments, field):
    @asynccontextmanager
    async def sessions():
        yield object()

    tools = {
        t.tool_name: t
        for t in enterprise_risk.enterprise_risk_tools(
            sessions, "owner", ModelingStorage(object()), object()
        )
    }
    result = asyncio.run(tools[name](**arguments))
    detail = result["content"][0]["json"]
    assert result["status"] == "error"
    assert detail["code"] == "MODEL_INPUT_INVALID" and detail["field"] == field
    assert "enterprise_risk_catalog()" in detail["recovery"]
