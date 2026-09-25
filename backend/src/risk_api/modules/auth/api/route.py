from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.api import handler
from risk_api.modules.auth.api.schemas import ResponseLogin, ResponseLogout, ResponseMe
from risk_api.modules.auth.errors import LOGIN_ERRORS, LOGOUT_ERRORS, SESSION_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/login",
    handler.login,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseLogin],
    responses=COMMON_ERROR_RESPONSES | LOGIN_ERRORS,
)
router.add_api_route(
    "/logout",
    handler.logout,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseLogout],
    responses=COMMON_ERROR_RESPONSES | LOGOUT_ERRORS,
)
router.add_api_route(
    "/me",
    handler.me,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseMe],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
