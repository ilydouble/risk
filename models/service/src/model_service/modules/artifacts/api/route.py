from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from model_service.modules.artifacts.api import handler
from model_service.modules.jobs.api.schemas import ResponseJob
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute, responses=ERROR_RESPONSES)
router.add_api_route(
    "/get", handler.artifact, methods=["POST"], response_model=Envelope[ResponseJob]
)
