"""Reconstruct bounded model context from server-owned, persisted Items."""

import hashlib
import json

from strands.types.content import Messages
from strands.types.tools import ToolResultContent

from risk_api.modules.assistant.protocol.items import ToolItem
from risk_api.modules.assistant.protocol.turns import Turn

HISTORY_CHAR_LIMIT = 32_000
HISTORY_TURN_LIMIT = 10


def _tool_messages(turn: Turn, item: ToolItem) -> Messages:
    if item.status not in {"completed", "failed"} or item.result is None or not item.name:
        return []
    try:
        arguments = json.loads(item.argumentsText)
    except ValueError:
        return []
    if not isinstance(arguments, dict):
        return []
    # Providers can reuse call IDs across requests. Namespace both sides of each stored pair.
    call_id = "history_" + hashlib.sha256(f"{turn.id}:{item.id}".encode()).hexdigest()[:32]
    content: list[ToolResultContent] = []
    for block in item.result if isinstance(item.result, list) else [item.result]:
        if isinstance(block, dict) and set(block) == {"text"} and isinstance(block["text"], str):
            content.append({"text": block["text"]})
        elif isinstance(block, dict) and set(block) == {"json"}:
            content.append({"json": block["json"]})
        else:
            # Persisted results are JSON; unfamiliar media blocks remain data, never fetched URLs.
            content.append({"json": block})
    return [
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": call_id,
                        "name": item.name,
                        "input": arguments,
                    }
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": call_id,
                        "status": "error" if item.status == "failed" else "success",
                        "content": content,
                    }
                }
            ],
        },
    ]


def conversation_messages(history: list[Turn]) -> Messages:
    retained: list[Messages] = []
    remaining = HISTORY_CHAR_LIMIT
    for turn in reversed(history):
        if turn.status != "completed":
            continue
        messages: Messages = []
        for item in turn.items:
            if item.kind == "user_message" and item.text:
                messages.append({"role": "user", "content": [{"text": item.text}]})
            elif item.kind == "agent_message" and item.text:
                messages.append({"role": "assistant", "content": [{"text": item.text}]})
            elif item.kind == "tool_call":
                messages.extend(_tool_messages(turn, item))
        if not messages or messages[0]["role"] != "user":
            continue
        # Count serialized tool arguments/results too; never truncate a UUID, result or call pair.
        size = len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))
        if size > remaining or len(retained) >= HISTORY_TURN_LIMIT:
            break
        remaining -= size
        retained.append(messages)
    return [message for turn_messages in reversed(retained) for message in turn_messages]
