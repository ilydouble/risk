from dishka.integrations.fastapi import FromDishka
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.graph.api.schemas import (
    GraphData,
    RequestGetDatasetGraph,
    RequestGetGraph,
    ResponseGetDatasetGraph,
    ResponseGetGraph,
)
from risk_api.modules.graph.dataset_service import DEMO_DATASET_ID, DatasetGraphService, demo_graph
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


async def get_dataset_graph(
    body: RequestGetDatasetGraph,
    request: Request,
    auth: FromDishka[AuthService],
    session: FromDishka[AsyncSession],
    service: FromDishka[GraphService],
) -> ApiEnvelope[ResponseGetDatasetGraph]:
    user = await authorize_request(request, auth)
    if body.datasetId == DEMO_DATASET_ID:
        graph = demo_graph(
            await service.get(body.companyId, body.lang, body.depth), body.companyId, body.depth
        )
    else:
        graph = await DatasetGraphService(session).get(
            user["user_id"], body.datasetId, body.companyId, body.depth
        )
    return success_response(ResponseGetDatasetGraph.model_validate(graph))
