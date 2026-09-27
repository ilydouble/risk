from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.overview.api.schemas import (
    OverviewDatasetDTO,
    OverviewSampleCompanyDTO,
    OverviewSamplingDTO,
    RequestGetOverview,
    RequestSearchOverviewCompany,
    ResponseGetOverview,
    ResponseSearchOverviewCompany,
)
from risk_api.modules.overview.query import OverviewSampleSearchQuery
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


async def search_companies(
    body: RequestSearchOverviewCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[OverviewService],
) -> ApiEnvelope[ResponseSearchOverviewCompany]:
    await authorize_request(request, auth)
    page = body.pagination
    dataset, sampling, samples, industry_codes, total = await service.search_samples(
        OverviewSampleSearchQuery(
            keyword=body.keyword,
            category=body.category,
            industry_code=body.industryCode,
            sort=body.sort,
            page=page.page,
            page_size=page.pageSize,
        )
    )
    return success_response(
        ResponseSearchOverviewCompany(
            items=[OverviewSampleCompanyDTO.model_validate(item) for item in samples],
            total=total,
            page=page.page,
            pageSize=page.pageSize,
            dataset=OverviewDatasetDTO.model_validate(dataset),
            sampling=OverviewSamplingDTO.model_validate(sampling),
            industryCodes=industry_codes,
        )
    )
