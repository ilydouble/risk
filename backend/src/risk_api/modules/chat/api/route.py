from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.chat.api.handler import complete
from risk_api.modules.chat.api.schemas import ResponseChat
from risk_api.modules.chat.errors import CHAT_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/complete",
    complete,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseChat],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | CHAT_ERRORS,
)
