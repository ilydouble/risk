"""The only translation from Strands stream payloads to public display items."""

import json
from typing import Any, Literal

from pydantic import ValidationError

from risk_api.modules.assistant.protocol.graph import CompanyGraphReference
from risk_api.modules.assistant.protocol.items import (
    AgentMessageItem,
    AgentReasoningItem,
    Item,
    ItemStatus,
    ToolItem,
)


class ItemProjector:
    def __init__(self) -> None:
        self.text: AgentReasoningItem | AgentMessageItem | None = None
        self.tools: dict[str, ToolItem] = {}
        self.answer = ""

    def project(self, event: dict[str, Any]) -> list[Item]:
        updates: list[Item] = []
        kind: Literal["reasoning", "agent_message"] = (
            "reasoning" if event.get("reasoningText") else "agent_message"
        )
        token = event.get("reasoningText") or event.get("data")
        if isinstance(token, str) and token:
            if self.text and self.text.kind != kind:
                self.text.status = ItemStatus.COMPLETED
                updates.append(self.text.model_copy(deep=True))
                self.text = None
            if self.text is None:
                self.text = AgentReasoningItem() if kind == "reasoning" else AgentMessageItem()
            self.text.text += token
            if kind == "agent_message":
                self.answer += token
            updates.append(self.text.model_copy(deep=True))
        tool = event.get("current_tool_use")
        if isinstance(tool, dict) and tool.get("toolUseId"):
            tool_id = tool["toolUseId"]
            item = self.tools.setdefault(
                tool_id, ToolItem(toolCallId=tool_id, name=tool.get("name", ""))
            )
            args = tool.get("input", "")
            item.argumentsText = (
                args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
            )
            updates.append(item.model_copy(deep=True))
        message = event.get("message", {})
        if message.get("role") == "assistant":
            if self.text:
                self.text.status = ItemStatus.COMPLETED
                updates.append(self.text.model_copy(deep=True))
                self.text = None
            for block in message.get("content", []):
                if "toolUse" in block:
                    tool = block["toolUse"]
                    item = self.tools.setdefault(
                        tool["toolUseId"], ToolItem(toolCallId=tool["toolUseId"], name=tool["name"])
                    )
                    item.argumentsText = json.dumps(tool["input"], ensure_ascii=False)
                    updates.append(item.model_copy(deep=True))
        # stream_async exposes tool results as message blocks; its internal ToolResultEvent
        # is not a public callback event in Strands 1.60.
        for block in message.get("content", []):
            result = block.get("toolResult")
            if isinstance(result, dict) and result.get("toolUseId") in self.tools:
                item = self.tools[result["toolUseId"]]
                item.result = result.get("content", [])
                item.status = (
                    ItemStatus.FAILED if result.get("status") == "error" else ItemStatus.COMPLETED
                )
                if item.status == ItemStatus.COMPLETED and item.name == "show_company_graph":
                    # Only this server-registered tool can produce a validated graph card.
                    for content in result.get("content", []):
                        if isinstance(content, dict) and "json" in content:
                            try:
                                item.graph = CompanyGraphReference.model_validate(content["json"])
                            except ValidationError:
                                pass
                updates.append(item.model_copy(deep=True))
        return updates
