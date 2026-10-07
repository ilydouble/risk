from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.overview.api import handler
from risk_api.modules.overview.api.schemas import (
    ResponseGetOverview,
    ResponseGetOverviewCompany,
    ResponseSearchOverviewCompany,
)
from risk_api.modules.overview.errors import NOT_FOUND_RESPONSE, UNAVAILABLE_RESPONSE
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
router.add_api_route(
    "/get-company",
    handler.get_company,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetOverviewCompany],
    responses=(COMMON_ERROR_RESPONSES | SESSION_ERRORS | UNAVAILABLE_RESPONSE | NOT_FOUND_RESPONSE),
)
router.add_api_route(
    "/search-companies",
    handler.search_companies,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseSearchOverviewCompany],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | UNAVAILABLE_RESPONSE,
)
