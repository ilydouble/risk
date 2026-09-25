from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.errors import NOT_FOUND_RESPONSE
from risk_api.modules.score.service import ScoreService
from risk_api.schemas import COMMON_ERROR_RESPONSES, ApiEnvelope, RequestGetScore, ResponseGetScore

router = APIRouter(route_class=DishkaRoute)


@router.post(
    "/get", response_model=ApiEnvelope[ResponseGetScore],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | NOT_FOUND_RESPONSE,
)
async def get(
    body: RequestGetScore,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ScoreService],
) -> ApiEnvelope[ResponseGetScore]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200,
        internal_code="SUCCESS",
        message="Demo snapshot",
        data=await service.get(body.companyId, body.lang),
    )
