from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from model_service.modules.decision.api.schemas import (
    RequestDecisionPredict,
    RequestDecisionPredictRecord,
    RequestDecisionStatus,
    ResponseDecisionPredict,
    ResponseDecisionStatus,
)
from model_service.modules.decision.errors import DecisionError
from model_service.modules.decision.service import DecisionService
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import success_response


async def status(
    body: RequestDecisionStatus, service: FromDishka[DecisionService]
) -> Envelope[ResponseDecisionStatus]:
    try:
        result = ResponseDecisionStatus(ready=True, model=service.info())
    except DecisionError as error:
        result = ResponseDecisionStatus(ready=False, model=None, errorCode=error.code)
    return success_response(result)


async def predict(
    body: RequestDecisionPredict, request: Request, service: FromDishka[DecisionService]
) -> Envelope[ResponseDecisionPredict]:
    result = await service.predict(
        body.input, request.state.request_id, expected_digest=body.expectedManifestSha256
    )
    return success_response(ResponseDecisionPredict(model=service.info(), prediction=result))


async def predict_record(
    body: RequestDecisionPredictRecord, request: Request, service: FromDishka[DecisionService]
) -> Envelope[ResponseDecisionPredict]:
    result = await service.predict_record(
        body.adapterId,
        body.adapterVersion,
        body.attributes,
        request.state.request_id,
        body.expectedManifestSha256,
    )
    return success_response(ResponseDecisionPredict(model=service.info(), prediction=result))
