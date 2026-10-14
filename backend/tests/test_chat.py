import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from risk_api.app import create_app
from risk_api.errors import AppError
from risk_api.modules.chat.api.schemas import RequestChat
from risk_api.modules.chat.service import ChatService


def call(handler, *, token="test-key"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await ChatService(
                http, "http://llm/v1/chat/completions", token, "qwen"
            ).complete([{"role": "user", "content": "你好"}])

    return asyncio.run(run())


def test_chat_upstream_contract():
    import json

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "qwen",
            "messages": [{"role": "user", "content": "你好"}],
            "max_tokens": 1024,
            "chat_template_kwargs": {"enable_thinking": False, "thinking": False},
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好！"}}]})

    reply = call(handler)
    assert reply.content == "你好！"
    assert reply.model == "qwen"
    assert reply.elapsed_ms >= 0


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
        [{"role": "user", "content": "x" * 8001}],
        [{"role": "user", "content": "x" * 8000}] * 5,
    ],
)
def test_chat_validates_bounded_user_conversations(messages):
    with pytest.raises(ValidationError):
        RequestChat(messages=messages)


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
