from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.graph.api.schemas import GraphData, RequestGetGraph, ResponseGetGraph
from risk_api.modules.graph.service import GraphService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


async def get(
    body: RequestGetGraph,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[GraphService],
) -> ApiEnvelope[ResponseGetGraph]:
    await authorize_request(request, auth)
    graph = await service.get(body.companyId, body.lang, body.depth)
    return success_response(
        ResponseGetGraph(graph=GraphData.model_validate(graph)), message="Demo graph"
    )
