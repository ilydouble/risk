from dishka.integrations.fastapi import FromDishka
from fastapi import Request
from fastapi.responses import StreamingResponse

from risk_api.modules.assistant.api.schemas import (
    RequestCancelTurn,
    RequestCreateConversation,
    RequestCreateTurn,
    RequestGetConversation,
    RequestListConversations,
    RequestTurnEvents,
    ResponseCancelTurn,
    ResponseCreateConversation,
    ResponseCreateTurn,
    ResponseGetConversation,
    ResponseListConversations,
)
from risk_api.modules.assistant.runtime import ModelSettings
from risk_api.modules.assistant.service import AssistantService
from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response
from risk_api.shared.config import settings


async def create_conversation(
    body: RequestCreateConversation,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> ApiEnvelope[ResponseCreateConversation]:
    user = await authorize_request(request, auth)
    return success_response(
        ResponseCreateConversation(
            conversation=await service.repository.create_conversation(user["user_id"])
        )
    )


async def list_conversations(
    body: RequestListConversations,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> ApiEnvelope[ResponseListConversations]:
    user = await authorize_request(request, auth)
    return success_response(
        ResponseListConversations(
            conversations=await service.repository.conversations(user["user_id"])
        )
    )


async def get_conversation(
    body: RequestGetConversation,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> ApiEnvelope[ResponseGetConversation]:
    user = await authorize_request(request, auth)
    return success_response(
        ResponseGetConversation(
            turns=await service.repository.history(user["user_id"], str(body.conversationId))
        )
    )


async def create_turn(
    body: RequestCreateTurn,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> ApiEnvelope[ResponseCreateTurn]:
    user = await authorize_request(request, auth)
    connection = body.connection
    model = ModelSettings(
        url=connection.url if connection else settings.llm_url,
        model=connection.model if connection else settings.llm_model,
        api_key=connection.apiKey if connection else settings.llm_api_key,
        max_tokens=body.maxTokens,
        connection_type=settings.llm_connection_type,
        thinking_enabled=settings.llm_thinking_enabled,
    )
    turn = await service.start(
        user["user_id"],
        str(body.conversationId),
        str(body.requestKey),
        body.message,
        model,
        request.state.request_id,
    )
    return success_response(ResponseCreateTurn(turn=turn))


async def cancel_turn(
    body: RequestCancelTurn,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> ApiEnvelope[ResponseCancelTurn]:
    user = await authorize_request(request, auth)
    return success_response(
        ResponseCancelTurn(turn=await service.cancel(user["user_id"], str(body.turnId)))
    )


async def turn_events(
    body: RequestTurnEvents,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[AssistantService],
) -> StreamingResponse:
    user = await authorize_request(request, auth)
    await service.repository.turn(user["user_id"], str(body.turnId))
    return StreamingResponse(
        service.events(user["user_id"], str(body.turnId), body.afterSequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
