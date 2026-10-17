import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from risk_api.modules.chat.service import ChatService
from risk_api.shared.api.model_connection import ModelConnection


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/v1/chat/completions",
        "http://169.254.169.254/v1/chat/completions",
        "https://example.com/admin",
        "https://user:password@example.com/v1/chat/completions",
        "https://example.com/v1/chat/completions?target=secret",
    ],
)
def test_model_connection_rejects_unsafe_endpoint(url: str) -> None:
    with pytest.raises(ValidationError):
        ModelConnection(url=url, model="sample")


def test_custom_model_uses_selected_url_without_changing_default() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            default = ChatService(
                client, "https://default.test/v1/chat/completions", "secret", "old"
            )
            connection = ModelConnection(url="https://example.com/v1/chat/completions", model="new")
            custom = default.configured(connection.url, connection.apiKey, connection.model)
            reply = await custom.complete([{"role": "user", "content": "ping"}])
            assert reply.model == "new"
            assert default.model == "old"

    asyncio.run(run())
    assert str(requests[0].url) == "https://example.com/v1/chat/completions"
    assert "authorization" not in requests[0].headers
    assert json.loads(requests[0].content)["model"] == "new"
    assert "chat_template_kwargs" not in json.loads(requests[0].content)
