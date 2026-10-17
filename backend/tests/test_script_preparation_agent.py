import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
from openai import AsyncOpenAI
from strands.models.openai import OpenAIModel

from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_prep.script_agent import propose_script
from risk_api.modules.data_prep.script_service import pack_inputs


def test_real_strands_loop_reads_inputs_target_logs_and_proposes_only_a_draft():
    requests = []
    calls = [
        ("read_inputs", {}),
        ("read_inputs", {"filename": "source.csv"}),
        ("read_target", {}),
        ("read_script_and_logs", {}),
        ("propose_python", {"code": "print('fixed draft')", "explanation": "修复类型转换"}),
    ]

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) <= len(calls):
            name, args = calls[len(requests) - 1]
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": f"call-{len(requests)}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }]}
            stop = "tool_calls"
        else:
            assert "001" in json.dumps(payload["messages"])
            assert "actual failure" in json.dumps(payload["messages"])
            assert "source.csv" in json.dumps(payload["messages"])
            message = {"role": "assistant", "content": "已提出修复脚本，尚未执行。"}
            stop = "stop"
        return httpx2.Response(200, json={
            "id": "script-agent-test", "object": "chat.completion", "created": 1,
            "model": "test", "choices": [{"index": 0, "message": message, "finish_reason": stop}],
        })

    async def run():
        source, files = pack_inputs([("source.csv", b"id\n001\n")])
        task = SimpleNamespace(source=source, files=files, script="print('old')",
                               requirements="IDs",
                               messages=[], revision=2)
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
            provider = AsyncOpenAI(api_key="test", base_url="https://example.com/v1",
                                   http_client=http)
            chat = Mock(spec=ChatService, token="test", model="test", require_token=False,
                        disable_thinking=False, url="https://example.com/v1/chat/completions")
            with patch("risk_api.modules.data_prep.script_agent.OpenAIModel", side_effect=(
                lambda **kw: OpenAIModel(client=provider, model_id=kw["model_id"],
                                        params=kw["params"])
            )):
                proposal = await propose_script(task, {"requiredFiles": ["train.json"]}, [{
                    "revision": 1, "status": "failed", "error": "actual failure",
                    "log": "line 3", "result": {},
                }], "修复脚本", chat, 4096)
            assert proposal["proposed"] and proposal["script"] == "print('fixed draft')"
            assert len(proposal["toolTrace"]) == 5
            assert task.script == "print('old')"
    asyncio.run(run())
    tools = {item["function"]["name"] for item in requests[0]["tools"]}
    assert tools == {"read_inputs", "read_target", "read_script_and_logs", "propose_python"}
    assert requests[0]["stream"] is False
