from dataclasses import dataclass
from time import perf_counter

import httpx

from risk_api.errors import AppError


@dataclass(frozen=True)
class ChatReply:
    content: str
    model: str
    elapsed_ms: int


class ChatService:
    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str,
        token: str,
        model: str,
        *,
        require_token: bool = True,
        disable_thinking: bool = True,
    ):
        self.http, self.url, self.token, self.model = http, url, token, model
        self.require_token = require_token
        self.disable_thinking = disable_thinking

    def configured(self, url: str, token: str, model: str) -> "ChatService":
        return ChatService(
            self.http, url, token, model, require_token=False, disable_thinking=False
        )

    async def complete(self, messages: list[dict[str, str]]) -> ChatReply:
        if self.require_token and not self.token.strip():
            raise AppError(503, "CHAT_NOT_CONFIGURED", "请配置后端 RISK_LLM_API_KEY")
        start = perf_counter()
        payload = {"model": self.model, "messages": messages, "max_tokens": 1024}
        if self.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False, "thinking": False}
        try:
            response = await self.http.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"} if self.token.strip() else {},
                json=payload,
            )
        except httpx.ConnectTimeout as error:
            raise AppError(
                503, "CHAT_UNREACHABLE", "连接大模型超时，请检查后端到模型服务的网络"
            ) from error
        except httpx.TimeoutException as error:
            raise AppError(504, "CHAT_TIMEOUT", "大模型响应超时，请检查模型服务负载") from error
        except httpx.RequestError as error:
            raise AppError(
                503, "CHAT_UNREACHABLE", "无法连接大模型，请检查后端到模型服务的网络"
            ) from error
        # Never expose upstream bodies: they may contain credentials or internal diagnostics.
        if response.status_code in {401, 403}:
            raise AppError(502, "CHAT_AUTH_FAILED", "大模型认证失败，请检查所选模型的密钥")
        if not response.is_success:
            raise AppError(
                502, "CHAT_UPSTREAM_ERROR", f"大模型服务返回 HTTP {response.status_code}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty answer")
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise AppError(502, "CHAT_INVALID_RESPONSE", "大模型返回格式异常或回答为空") from error
        return ChatReply(content, self.model, round((perf_counter() - start) * 1000))
