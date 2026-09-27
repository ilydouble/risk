from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.overview.api import handler
from risk_api.modules.overview.api.schemas import ResponseGetOverview
from risk_api.modules.overview.errors import UNAVAILABLE_RESPONSE
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/get",
    handler.get,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetOverview],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | UNAVAILABLE_RESPONSE,
)
