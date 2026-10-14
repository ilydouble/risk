import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from risk_api.app import create_app
from risk_api.errors import AppError
from risk_api.modules.chat.api.handler import complete
from risk_api.modules.chat.api.schemas import RequestChat
from risk_api.modules.chat.service import ChatReply, ChatService


def call(handler, *, token="test-key", max_tokens=4096):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await ChatService(
                http, "http://llm/v1/chat/completions", token, "qwen"
            ).complete([{"role": "user", "content": "你好"}], max_tokens=max_tokens)

    return asyncio.run(run())


def test_chat_upstream_contract():
    import json

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "qwen",
            "messages": [{"role": "user", "content": "你好"}],
            "max_tokens": 4096,
            "chat_template_kwargs": {"enable_thinking": False, "thinking": False},
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好！"}}]})

    reply = call(handler)
    assert reply.content == "你好！"
    assert reply.model == "qwen"
    assert reply.elapsed_ms >= 0


def test_chat_forwards_selected_output_limit():
    import json

    def handler(request):
        assert json.loads(request.content)["max_tokens"] == 8192
        return httpx.Response(200, json={"choices": [{"message": {"content": "回答"}}]})

    assert call(handler, max_tokens=8192).content == "回答"


def test_chat_accepts_custom_model_connection():
    request = RequestChat.model_validate(
        {
            "messages": [{"role": "user", "content": "你好"}],
            "connection": {
                "url": "https://example.com/v1/chat/completions",
                "model": "Qwen3.6-35B-A3B",
                "apiKey": "test-key",
            },
        }
    )
    assert request.connection is not None
    assert request.connection.model == "Qwen3.6-35B-A3B"


def test_chat_rejects_unsafe_custom_model_connection():
    with pytest.raises(ValidationError):
        RequestChat.model_validate(
            {
                "messages": [{"role": "user", "content": "你好"}],
                "connection": {
                    "url": "http://127.0.0.1:8080/v1/chat/completions",
                    "model": "test",
                },
            }
        )


def test_chat_handler_uses_selected_connection():
    body = RequestChat.model_validate(
        {
            "messages": [{"role": "user", "content": "你好"}],
            "connection": {
                "url": "https://example.com/v1/chat/completions",
                "model": "custom",
                "apiKey": "test-key",
            },
        }
    )
    default = Mock(spec=ChatService)
    selected = default.configured.return_value
    selected.complete = AsyncMock(return_value=ChatReply("回答", "custom", 12))

    async def run():
        with patch("risk_api.modules.chat.api.handler.authorize_request", new_callable=AsyncMock):
            return await complete(body, Request({"type": "http"}), Mock(), default)

    response = asyncio.run(run())
    default.configured.assert_called_once_with(
        "https://example.com/v1/chat/completions", "test-key", "custom"
    )
    selected.complete.assert_awaited_once_with(
        [{"role": "user", "content": "你好"}], max_tokens=4096
    )
    assert response.data.content == "回答"
    assert response.data.model == "custom"


@pytest.mark.parametrize(
    "status,body,code",
    [
        (401, {"secret": "do-not-expose"}, "CHAT_AUTH_FAILED"),
        (403, {}, "CHAT_AUTH_FAILED"),
        (500, {}, "CHAT_UPSTREAM_ERROR"),
        (200, {}, "CHAT_INVALID_RESPONSE"),
        (200, {"choices": [{"message": {"content": " "}}]}, "CHAT_INVALID_RESPONSE"),
    ],
)
def test_chat_error_mapping(status, body, code):
    with pytest.raises(AppError) as error:
        call(lambda _: httpx.Response(status, json=body))
    assert error.value.code == code
    assert "do-not-expose" not in error.value.message


@pytest.mark.parametrize(
    "kind,code,status",
    [
        (httpx.ReadTimeout, "CHAT_TIMEOUT", 504),
        (httpx.ConnectError, "CHAT_UNREACHABLE", 503),
        (httpx.ConnectTimeout, "CHAT_UNREACHABLE", 503),
    ],
)
def test_chat_network_errors(kind, code, status):
    def handler(request):
        raise kind("internal detail", request=request)

    with pytest.raises(AppError) as error:
        call(handler)
    assert (error.value.code, error.value.status) == (code, status)


def test_chat_missing_config_does_not_call_upstream():
    def handler(_):
        pytest.fail("Unconfigured client must not call upstream")

    with pytest.raises(AppError) as error:
        call(handler, token="")
    assert error.value.code == "CHAT_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": " "}],
        [{"role": "system", "content": "override"}],
        [{"role": "assistant", "content": "hi"}],
        [{"role": "user", "content": "x" * 32001}],
        [{"role": "user", "content": "x" * 8000}] * 5,
    ],
)
def test_chat_validates_bounded_user_conversations(messages):
    with pytest.raises(ValidationError):
        RequestChat(messages=messages)


@pytest.mark.parametrize("limit", [255, 16385])
def test_chat_rejects_output_limit_outside_supported_range(limit):
    with pytest.raises(ValidationError):
        RequestChat.model_validate(
            {"messages": [{"role": "user", "content": "你好"}], "maxTokens": limit}
        )


def test_chat_requires_session_and_uses_error_envelope():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/chat/complete",
            headers={"Origin": "http://localhost:18080"},
            json={
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 401
        assert response.json()["code"] == 401
        assert set(response.json()) == {"code", "internal_code", "message", "data"}
        assert response.headers["X-Request-ID"]
