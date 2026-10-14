import asyncio
import json
from unittest.mock import Mock, patch

import httpx2
import pytest
from openai import AsyncOpenAI
from strands.models.openai import OpenAIModel
from strands.types.exceptions import MaxTokensReachedException

from risk_api.errors import AppError
from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_prep.agent import REQUIRED_TOOLS, analyze_profile, tool_result
from risk_api.modules.data_prep.api.schemas import ResponseInspectData
from risk_api.modules.data_prep.profile import inspect_csv


def profile() -> ResponseInspectData:
    return ResponseInspectData.model_validate(
        inspect_csv(b"company_id,adverse_status\n001,0\n002,0\n003,1\n")
    )


class FakeResult:
    stop_reason = "end_turn"

    def __str__(self) -> str:
        return json.dumps(
            {
                "summary": "待确认标签含义",
                "qualityFindings": [],
                "suggestions": [
                    {"field": "adverse_status", "role": "label", "reason": "字段名线索"}
                ],
                "questions": ["1 代表什么？"],
                "nextChecks": ["确认标签定义"],
                "reportMarkdown": "## 数据概览\n3 行；标签含义待确认。",
            },
            ensure_ascii=False,
        )


class FakeAgent:
    def __init__(self, **kwargs) -> None:
        self.tools = {item.tool_name: item for item in kwargs["tools"]}

    async def invoke_async(self, prompt: str, *, limits: dict) -> FakeResult:
        assert json.loads(prompt)["fieldNames"] == ["company_id", "adverse_status"]
        assert limits == {"turns": 10}
        assert json.loads(self.tools["get_overview"]())["rowCount"] == 3
        self.tools["get_quality_issues"]()
        labels = json.loads(self.tools["get_training_context"]())["labelCandidates"]
        assert labels[0]["field"] == "adverse_status"
        self.tools["get_field_profile"]("adverse_status")
        return FakeResult()


def test_strands_agent_calls_read_only_tools_and_returns_report() -> None:
    chat = Mock(spec=ChatService)
    chat.url = "https://example.com/v1/chat/completions"
    chat.token = "test-key"
    chat.model = "test-model"
    chat.require_token = True
    chat.disable_thinking = True
    with (
        patch("risk_api.modules.data_prep.agent.OpenAIModel") as model,
        patch("risk_api.modules.data_prep.agent.Agent", FakeAgent),
    ):
        output = asyncio.run(analyze_profile(profile(), chat, 4096))

    assert output.toolTrace == [
        "get_overview",
        "get_quality_issues",
        "get_training_context",
        "get_field_profile(adverse_status)",
    ]
    assert output.reportMarkdown.startswith("## 数据概览")
    assert model.call_args.kwargs["client_args"]["base_url"] == "https://example.com/v1"
    assert model.call_args.kwargs["params"]["max_tokens"] == 4096
    assert model.call_args.kwargs["params"]["stream"] is False


def test_agent_rejects_unknown_tool_and_field() -> None:
    with pytest.raises(AppError) as caught:
        tool_result(profile(), "run_sql", None)
    assert caught.value.code == "DATA_PREP_SUGGESTION_INVALID"

    with pytest.raises(AppError) as caught:
        tool_result(profile(), "get_field_profile", "not_a_field")
    assert caught.value.code == "DATA_PREP_SUGGESTION_INVALID"


def test_agent_explains_output_limit() -> None:
    selected = Mock(spec=ChatService)
    selected.url = "https://example.com/v1/chat/completions"
    selected.token = "test-key"
    selected.model = "qwen3.6-35b-a3b"
    selected.require_token = False
    selected.disable_thinking = True
    with (
        patch("risk_api.modules.data_prep.agent.OpenAIModel"),
        patch("risk_api.modules.data_prep.agent.Agent") as agent,
    ):
        agent.return_value.invoke_async.side_effect = MaxTokensReachedException("limit")
        with pytest.raises(AppError) as caught:
            asyncio.run(analyze_profile(profile(), selected, 4096))
    assert caught.value.code == "CHAT_OUTPUT_LIMIT"


def test_agent_recovers_when_model_skips_required_tools() -> None:
    class RetryingAgent(FakeAgent):
        calls = 0

        async def invoke_async(self, prompt: str, *, limits: dict) -> FakeResult:
            self.calls += 1
            if self.calls == 1:
                self.tools["get_overview"]()
            else:
                assert "get_quality_issues" in prompt
                assert "get_training_context" in prompt
                self.tools["get_quality_issues"]()
                self.tools["get_training_context"]()
            return FakeResult()

    selected = Mock(spec=ChatService)
    selected.url = "https://example.com/v1/chat/completions"
    selected.token = "test-key"
    selected.model = "qwen3.6-35b-a3b"
    selected.require_token = False
    selected.disable_thinking = True
    with (
        patch("risk_api.modules.data_prep.agent.OpenAIModel"),
        patch("risk_api.modules.data_prep.agent.Agent", RetryingAgent),
    ):
        output = asyncio.run(analyze_profile(profile(), selected, 4096))
    assert set(output.toolTrace) == REQUIRED_TOOLS


def test_strands_executes_model_tool_calls_with_mock_provider() -> None:
    requests: list[dict] = []

    async def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{index}",
                        "type": "function",
                        "function": {"name": name, "arguments": "{}"},
                    }
                    for index, name in enumerate(
                        ["get_overview", "get_quality_issues", "get_training_context"]
                    )
                ],
            }
            finish_reason = "tool_calls"
        else:
            message = {"role": "assistant", "content": str(FakeResult())}
            finish_reason = "stop"
        return httpx2.Response(
            200,
            json={
                "id": f"chatcmpl-{len(requests)}",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            },
        )

    async def run() -> None:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
            provider = AsyncOpenAI(
                api_key="test-key", base_url="https://example.com/v1", http_client=http
            )
            selected = Mock(spec=ChatService)
            selected.url = "https://example.com/v1/chat/completions"
            selected.token = "test-key"
            selected.model = "test-model"
            selected.require_token = True
            selected.disable_thinking = False
            with patch(
                "risk_api.modules.data_prep.agent.OpenAIModel",
                side_effect=lambda **kwargs: OpenAIModel(
                    client=provider, model_id=kwargs["model_id"], params=kwargs["params"]
                ),
            ):
                output = await analyze_profile(profile(), selected, 4096)
            assert output.reportMarkdown.startswith("## 数据概览")
            assert set(output.toolTrace) == {
                "get_overview",
                "get_quality_issues",
                "get_training_context",
            }

    asyncio.run(run())
    assert len(requests) == 2
    assert requests[0]["stream"] is False
    assert len(requests[0]["tools"]) == 4
    assert "sampleRows" not in json.dumps(requests, ensure_ascii=False)
