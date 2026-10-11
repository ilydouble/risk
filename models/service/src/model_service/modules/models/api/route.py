from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from model_service.modules.models.api import handler
from model_service.modules.models.api.schemas import (
    ResponseCapabilities,
    ResponsePredict,
    ResponseRuntime,
)
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute, responses=ERROR_RESPONSES)
router.add_api_route(
    "/predict", handler.predict, methods=["POST"], response_model=Envelope[ResponsePredict]
)
router.add_api_route(
    "/capabilities",
    handler.model_capabilities,
    methods=["POST"],
    response_model=Envelope[ResponseCapabilities],
)

router.add_api_route(
    "/runtime", handler.runtime, methods=["POST"], response_model=Envelope[ResponseRuntime]
)
