from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.company.errors import NOT_FOUND_RESPONSE
from risk_api.modules.score.api import handler
from risk_api.modules.score.api.schemas import ResponseGetScore
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/get",
    handler.get,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetScore],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | NOT_FOUND_RESPONSE,
)
