from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.data_qa.api.schemas import (
    RequestAskData,
    RequestDataQACatalog,
    ResponseAskData,
    ResponseDataQACatalog,
)
from risk_api.modules.data_qa.service import DataQAService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def catalog(
    _: RequestDataQACatalog,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DataQAService],
) -> ApiEnvelope[ResponseDataQACatalog]:
    identity = await authorize_request(request, auth)
    return success_response(
        ResponseDataQACatalog.model_validate(await service.catalog(identity["user_id"]))
    )


async def ask(
    body: RequestAskData,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DataQAService],
) -> ApiEnvelope[ResponseAskData]:
    identity = await authorize_request(request, auth)
    return success_response(
        ResponseAskData.model_validate(
            await service.ask(
                identity["user_id"],
                body.question,
                str(body.datasetId) if body.datasetId else None,
                str(body.modelId) if body.modelId else None,
            )
        )
    )
