import pytest
from pydantic import TypeAdapter

from risk_api.modules.assistant.projector import ItemProjector
from risk_api.modules.assistant.protocol.items import (
    AgentMessageItem,
    AgentReasoningItem,
    Item,
    UserMessageItem,
)


@pytest.mark.parametrize(
    ("kind", "item_type"),
    [
        ("user_message", UserMessageItem),
        ("reasoning", AgentReasoningItem),
        ("agent_message", AgentMessageItem),
    ],
)
def test_existing_text_item_json_remains_compatible(kind, item_type):
    payload = {"id": "existing-item", "kind": kind, "status": "completed", "text": "已有内容"}
    item = TypeAdapter(Item).validate_python(payload)
    assert isinstance(item, item_type)
    assert item.model_dump(mode="json") == payload


def test_reasoning_and_answers_remain_distinct_across_tool_calls():
    projector = ItemProjector()
    items = {}
    for event in [
        {"reasoningText": "先分析"},
        {"reasoningText": "再查询"},
        {"data": "正在查询。"},
        {"current_tool_use": {"toolUseId": "call", "name": "current_time", "input": "{}"}},
        {"message": {"role": "assistant", "content": []}},
        {"message": {"role": "user", "content": [
            {"toolResult": {"toolUseId": "call", "status": "success", "content": []}},
        ]}},
        {"reasoningText": "根据结果"},
        {"data": "最终回答。"},
        {"message": {"role": "assistant", "content": []}},
    ]:
        for item in projector.project(event):
            items[item.id] = item
    assert [item.kind for item in items.values()] == [
        "reasoning", "agent_message", "tool_call", "reasoning", "agent_message",
    ]
    reasoning = [item for item in items.values() if isinstance(item, AgentReasoningItem)]
    assert [item.text for item in reasoning] == ["先分析再查询", "根据结果"]
    assert all(item.status == "completed" for item in items.values())
    assert projector.answer == "正在查询。最终回答。"
