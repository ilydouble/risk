from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.data_qa.api import handler
from risk_api.modules.data_qa.api.schemas import ResponseAskData, ResponseDataQACatalog
from risk_api.modules.data_qa.errors import DATA_QA_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/catalog",
    handler.catalog,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseDataQACatalog],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_QA_ERRORS,
)
router.add_api_route(
    "/ask",
    handler.ask,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseAskData],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_QA_ERRORS,
)
