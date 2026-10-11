from dishka.integrations.fastapi import FromDishka

from model_service.modules.models.api.schemas import (
    RequestCapabilities,
    RequestPredict,
    ResponseCapabilities,
    ResponsePredict,
)
from model_service.modules.models.service import Runtime
from model_service.runners.registry import capabilities
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import success_response


async def predict(body: RequestPredict, runtime: FromDishka[Runtime]) -> Envelope[ResponsePredict]:
    return success_response(
        ResponsePredict.model_validate(
            {"items": await runtime.predict(str(body.jobId), body.companyIds)}
        )
    )


async def model_capabilities(body: RequestCapabilities) -> Envelope[ResponseCapabilities]:
    return success_response(ResponseCapabilities.model_validate({"items": capabilities()}))
