from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.api.schemas import CompanyDTO
from risk_api.modules.score.api.schemas import RequestGetScore, ResponseGetScore, ScoreDetail
from risk_api.modules.score.service import ScoreService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success


async def get(
    body: RequestGetScore,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ScoreService],
) -> ApiEnvelope[ResponseGetScore]:
    await authorize_request(request, auth)
    company, detail = await service.get(body.companyId, body.lang)
    return success(
        ResponseGetScore(
            company=CompanyDTO.model_validate(company.summary),
            detail=ScoreDetail.model_validate(detail),
        ),
        message="Demo snapshot",
    )
