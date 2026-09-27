from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.overview.api.schemas import RequestGetOverview, ResponseGetOverview
from risk_api.modules.overview.service import OverviewService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def get(
    _: RequestGetOverview,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[OverviewService],
) -> ApiEnvelope[ResponseGetOverview]:
    await authorize_request(request, auth)
    return success_response(ResponseGetOverview.model_validate(await service.get()))
