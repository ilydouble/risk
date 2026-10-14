from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.chat.api.schemas import RequestChat, ResponseChat
from risk_api.modules.chat.service import ChatService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def complete(
    body: RequestChat,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ChatService],
) -> ApiEnvelope[ResponseChat]:
    await authorize_request(request, auth)
    reply = await service.complete([message.model_dump() for message in body.messages])
    return success_response(
        ResponseChat(content=reply.content, model=reply.model, elapsedMs=reply.elapsed_ms)
    )
