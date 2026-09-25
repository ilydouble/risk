from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.errors import NOT_FOUND_RESPONSE
from risk_api.modules.company.service import CompanyService
from risk_api.schemas import (
    COMMON_ERROR_RESPONSES,
    ApiEnvelope,
    RequestGetCompany,
    RequestSearchCompany,
    ResponseGetCompany,
    ResponseSearchCompany,
)

router = APIRouter(route_class=DishkaRoute)


@router.post(
    "/search", response_model=ApiEnvelope[ResponseSearchCompany],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
async def search(
    body: RequestSearchCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[CompanyService],
) -> ApiEnvelope[ResponseSearchCompany]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200, internal_code="SUCCESS", message="OK", data=await service.search(body)
    )


@router.post(
    "/get", response_model=ApiEnvelope[ResponseGetCompany],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | NOT_FOUND_RESPONSE,
)
async def get(
    body: RequestGetCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[CompanyService],
) -> ApiEnvelope[ResponseGetCompany]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200, internal_code="SUCCESS", message="OK", data=await service.get(body.id)
    )
