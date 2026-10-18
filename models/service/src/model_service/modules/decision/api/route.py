from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from model_service.modules.decision.api import handler
from model_service.modules.decision.api.schemas import (
    ResponseDecisionPredict,
    ResponseDecisionStatus,
)
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute, responses=ERROR_RESPONSES)
router.add_api_route(
    "/status", handler.status, methods=["POST"], response_model=Envelope[ResponseDecisionStatus]
)
router.add_api_route(
    "/predict", handler.predict, methods=["POST"], response_model=Envelope[ResponseDecisionPredict]
)
router.add_api_route(
    "/predict-record",
    handler.predict_record,
    methods=["POST"],
    response_model=Envelope[ResponseDecisionPredict],
)
