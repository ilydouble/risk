from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.decision.api import schemas as dto
from risk_api.modules.decision.service import DecisionService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def catalog(
    body: dto.RequestFinancialCatalog,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponseFinancialCatalog]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponseFinancialCatalog.model_validate(await service.catalog(user["user_id"]))
    )


async def companies(
    body: dto.RequestFinancialCompanies,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponseFinancialCompanies]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponseFinancialCompanies.model_validate(
            await service.companies(
                user["user_id"],
                str(body.datasetId),
                body.keyword,
                body.pagination.page,
                body.pagination.pageSize,
            )
        )
    )


async def predict(
    body: dto.RequestPredictFinancialCompany,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponsePredictFinancialCompany]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponsePredictFinancialCompany(
            prediction=await service.predict_company(
                user["user_id"],
                str(body.requestKey),
                str(body.datasetId),
                body.recordId,
            )
        )
    )


async def preview(
    body: dto.RequestPreviewFinancialInput,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponsePreviewFinancialInput]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponsePreviewFinancialInput(
            prediction=await service.predict_input(
                user["user_id"],
                str(body.requestKey),
                body.input,
                body.sourceLabel,
            )
        )
    )


async def get(
    body: dto.RequestGetFinancialPrediction,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponseGetFinancialPrediction]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponseGetFinancialPrediction(
            prediction=await service.get(user["user_id"], str(body.predictionId))
        )
    )


async def history(
    body: dto.RequestListFinancialPredictions,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DecisionService],
) -> ApiEnvelope[dto.ResponseListFinancialPredictions]:
    user = await authorize_request(request, auth)
    return success_response(
        dto.ResponseListFinancialPredictions.model_validate(
            await service.history(
                user["user_id"],
                body.pagination.page,
                body.pagination.pageSize,
            )
        )
    )
