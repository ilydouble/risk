from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.benchmark.api.schemas import (
    RequestEvaluationBenchmark,
    RequestExplainBenchmark,
    RequestGetBenchmark,
    RequestGraphBenchmark,
    RequestModelCardBenchmark,
    RequestPredictBenchmark,
    RequestSearchBenchmark,
    ResponseEvaluationBenchmark,
    ResponseExplainBenchmark,
    ResponseGetBenchmark,
    ResponseGraphBenchmark,
    ResponseModelCardBenchmark,
    ResponsePredictBenchmark,
    ResponseSearchBenchmark,
)
from risk_api.modules.benchmark.service import BenchmarkService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def search(
    body: RequestSearchBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseSearchBenchmark]:
    await authorize_request(request, auth)
    items, total = service.search(body.keyword, body.pagination.page, body.pagination.pageSize)
    return success_response(
        ResponseSearchBenchmark.model_validate(
            {
                "items": items,
                "total": total,
                "page": body.pagination.page,
                "pageSize": body.pagination.pageSize,
            }
        )
    )


async def get(
    body: RequestGetBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseGetBenchmark]:
    await authorize_request(request, auth)
    return success_response(ResponseGetBenchmark.model_validate(service.get(body.id)))


async def predict(
    body: RequestPredictBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponsePredictBenchmark]:
    await authorize_request(request, auth)
    card = service.model_card()
    return success_response(
        ResponsePredictBenchmark.model_validate(
            {"predictions": service.predict(body.companyIds), "threshold": card["threshold"]}
        )
    )


async def explain(
    body: RequestExplainBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseExplainBenchmark]:
    await authorize_request(request, auth)
    result = await service.explain(body.id)
    return success_response(
        ResponseExplainBenchmark.model_validate(
            {
                "companyId": result["company_id"],
                "riskProbability": result["risk_probability"],
                "method": result["method"],
                "interpretation": result["interpretation"],
                "features": result["features"],
                "incomingEdgeCount": result["incoming_edge_count"],
            }
        )
    )


async def graph(
    body: RequestGraphBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseGraphBenchmark]:
    await authorize_request(request, auth)
    return success_response(
        ResponseGraphBenchmark.model_validate(service.graph(body.id, body.limit))
    )


async def evaluation(
    _: RequestEvaluationBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseEvaluationBenchmark]:
    await authorize_request(request, auth)
    return success_response(ResponseEvaluationBenchmark.model_validate(service.evaluation()))


async def model_card(
    _: RequestModelCardBenchmark,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[BenchmarkService],
) -> ApiEnvelope[ResponseModelCardBenchmark]:
    await authorize_request(request, auth)
    return success_response(ResponseModelCardBenchmark.model_validate(service.model_card()))
