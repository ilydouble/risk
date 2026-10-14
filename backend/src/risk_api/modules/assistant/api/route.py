from typing import Literal

from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from risk_api.modules.assistant.api import handler
from risk_api.modules.assistant.api.schemas import (
    ResponseCancelTurn,
    ResponseCreateConversation,
    ResponseCreateTurn,
    ResponseGetConversation,
    ResponseListConversations,
    ResponseTurnEvent,
)
from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope, ErrorEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


router = APIRouter(route_class=DishkaRoute)
errors = (
    COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | {
        404: {"model": ErrorEnvelope[Literal[404], Literal["ASSISTANT_NOT_FOUND"]]},
        409: {
            "model": ErrorEnvelope[
                Literal[409], Literal["ASSISTANT_BUSY", "ASSISTANT_KEY_CONFLICT"]
            ]
        },
        503: {"model": ErrorEnvelope[Literal[503], Literal["ASSISTANT_CAPACITY"]]},
    }
)
router.add_api_route(
    "/conversations/create",
    handler.create_conversation,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCreateConversation],
    responses=errors,
)
router.add_api_route(
    "/conversations/list",
    handler.list_conversations,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseListConversations],
    responses=errors,
)
router.add_api_route(
    "/conversations/get",
    handler.get_conversation,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetConversation],
    responses=errors,
)
router.add_api_route(
    "/turns/create",
    handler.create_turn,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCreateTurn],
    responses=errors,
)
router.add_api_route(
    "/turns/cancel",
    handler.cancel_turn,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCancelTurn],
    responses=errors,
)
router.add_api_route(
    "/turns/events",
    handler.turn_events,
    methods=["POST"],
    response_class=EventStreamResponse,
    responses=errors
    | {
        200: {
            "model": ResponseTurnEvent,
            "description": "Each SSE data field is a ResponseTurnEvent",
        }
    },
)
