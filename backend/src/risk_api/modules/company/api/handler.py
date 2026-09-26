from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.api.schemas import (
    CompanyDTO,
    CompanyProfile,
    RequestGetCompany,
    RequestSearchCompany,
    ResponseGetCompany,
    ResponseSearchCompany,
)
from risk_api.modules.company.query import CompanySearchQuery
from risk_api.modules.company.service import CompanyService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def search(
    body: RequestSearchCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[CompanyService],
) -> ApiEnvelope[ResponseSearchCompany]:
    await authorize_request(request, auth)
    page = body.pagination
    companies, total = await service.search(
        CompanySearchQuery(
            keyword=body.keyword,
            region=body.region,
            sector=body.sector,
            risks=tuple(body.risks),
            sort=body.sort,
            page=page.page,
            page_size=page.pageSize,
        )
    )
    return success_response(
        ResponseSearchCompany(
            items=[CompanyDTO.model_validate(company.summary) for company in companies],
            total=total,
            page=page.page,
            pageSize=page.pageSize,
        )
    )


async def get(
    body: RequestGetCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[CompanyService],
) -> ApiEnvelope[ResponseGetCompany]:
    await authorize_request(request, auth)
    company = await service.get_model(body.id)
    return success_response(
        ResponseGetCompany(
            company=CompanyDTO.model_validate(company.summary),
            profile=CompanyProfile.model_validate(company.profile),
        )
    )
