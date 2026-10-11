from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from model_service.modules.jobs.api import handler
from model_service.modules.jobs.api.schemas import ResponseEvents, ResponseJob
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute, responses=ERROR_RESPONSES)
router.add_api_route(
    "/submit", handler.submit, methods=["POST"], response_model=Envelope[ResponseJob]
)
router.add_api_route("/get", handler.get, methods=["POST"], response_model=Envelope[ResponseJob])
router.add_api_route(
    "/cancel", handler.cancel, methods=["POST"], response_model=Envelope[ResponseJob]
)
router.add_api_route(
    "/events", handler.events, methods=["POST"], response_model=Envelope[ResponseEvents]
)
