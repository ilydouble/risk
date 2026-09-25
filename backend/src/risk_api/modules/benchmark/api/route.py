from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.benchmark.api import handler
from risk_api.modules.benchmark.api.schemas import (
    ResponseEvaluationBenchmark,
    ResponseExplainBenchmark,
    ResponseGetBenchmark,
    ResponseGraphBenchmark,
    ResponseModelCardBenchmark,
    ResponsePredictBenchmark,
    ResponseSearchBenchmark,
)
from risk_api.modules.benchmark.errors import BENCHMARK_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
errors = COMMON_ERROR_RESPONSES | SESSION_ERRORS | BENCHMARK_ERRORS
for path, endpoint, model in (
    ("/search", handler.search, ApiEnvelope[ResponseSearchBenchmark]),
    ("/get", handler.get, ApiEnvelope[ResponseGetBenchmark]),
    ("/predict", handler.predict, ApiEnvelope[ResponsePredictBenchmark]),
    ("/explain", handler.explain, ApiEnvelope[ResponseExplainBenchmark]),
    ("/graph", handler.graph, ApiEnvelope[ResponseGraphBenchmark]),
    ("/evaluation", handler.evaluation, ApiEnvelope[ResponseEvaluationBenchmark]),
    ("/model-card", handler.model_card, ApiEnvelope[ResponseModelCardBenchmark]),
):
    router.add_api_route(path, endpoint, methods=["POST"], response_model=model, responses=errors)
