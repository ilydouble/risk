"""Read-only demo company tools. Each invocation owns its database session."""

import logging
from typing import Any, Literal

from neo4j import AsyncDriver
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.assistant.protocol.graph import CompanyGraphReference, GraphSummary
from risk_api.modules.assistant.tools.company_arguments import (
    SearchCompaniesInput,
    ShowCompanyGraphInput,
)
from risk_api.modules.company.query import CompanySearchQuery
from risk_api.modules.company.repository import CompanyRepository
from risk_api.modules.company.service import CompanyService
from risk_api.modules.graph.dataset_service import DEMO_DATASET_ID, DatasetGraphService, demo_graph
from risk_api.modules.graph.repository import GraphRepository
from risk_api.modules.graph.service import GraphService

logger = logging.getLogger(__name__)


def failure(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}


class CompanyGraphTools:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], driver: AsyncDriver):
        self.sessions = sessions
        self.driver = driver

    def build(self, lang: Literal["zh", "en"], owner: str = "") -> list[AgentTool]:
        @tool(inputSchema={"json": SearchCompaniesInput.model_json_schema()})
        async def search_companies(keyword: str) -> dict[str, Any]:
            """Find demo companies by name or registration number before showing a graph.

            Args:
                keyword: Company name or registration number. If multiple companies match,
                    ask the user to choose. Never guess a company ID. Returns at most 10 matches.
            """
            try:
                keyword = SearchCompaniesInput(keyword=keyword).keyword
            except ValidationError:
                return failure(
                    "INVALID_ARGUMENT", "Provide a company keyword of 1 to 100 characters"
                )
            try:
                async with self.sessions() as session:
                    companies, total = await CompanyService(CompanyRepository(session)).search(
                        CompanySearchQuery(keyword.strip(), "all", "all", (), "score_desc", 1, 10)
                    )
                    return {
                        "status": "success",
                        "content": [
                            {
                                "json": {
                                    "companies": [
                                        {
                                            "companyId": c.id,
                                            "name": c.name_en if lang == "en" else c.name_cn,
                                            "registrationNumber": c.reg_no,
                                        }
                                        for c in companies
                                    ],
                                    "total": total,
                                    "truncated": total > len(companies),
                                    "demo": True,
                                    "datasetId": DEMO_DATASET_ID,
                                }
                            }
                        ],
                    }
            except Exception as exc:
                logger.warning(
                    "assistant.company_search_failed", extra={"cause_type": type(exc).__name__}
                )
                return failure("COMPANY_LOOKUP_UNAVAILABLE", "Company lookup is unavailable")

        @tool(inputSchema={"json": ShowCompanyGraphInput.model_json_schema()})
        async def show_company_graph(
            dataset_id: str, company_id: str, depth: int = 1
        ) -> dict[str, Any]:
            """Show source relationships for an enterprise in an explicitly selected dataset.

            Args:
                dataset_id: Exact datasetId from enterprise_risk_catalog, enterprise_risk_predict,
                    enterprise_risk_companies or asset_catalog. For shared demos use the datasetId
                    returned by search_companies. Never use modelId/runId or guess the dataset.
                company_id: Original company ID within that dataset. Do not substitute demo IDs.
                depth: Logical entity hops (1 to 3), default 1. Groups count as one expansion;
                    events are attached evidence. This is source data, not model attribution.
            """
            try:
                arguments = ShowCompanyGraphInput(
                    dataset_id=dataset_id, company_id=company_id, depth=depth
                )
                dataset_id, company_id, depth = (
                    arguments.dataset_id,
                    arguments.company_id,
                    arguments.depth,
                )
            except ValidationError:
                return failure(
                    "INVALID_ARGUMENT",
                    "An explicit dataset_id, company_id and depth from 1 to 3 are required",
                )
            try:
                # Agent tasks outlive the HTTP request and can run tools concurrently.
                # Never capture a request-scoped SQLAlchemy session in these closures.
                async with self.sessions() as session:
                    if dataset_id == DEMO_DATASET_ID:
                        companies = CompanyService(CompanyRepository(session))
                        raw = await GraphService(companies, GraphRepository(self.driver)).get(
                            company_id, lang, depth
                        )
                        graph = demo_graph(raw, company_id, depth)
                        company = await companies.get_model(company_id)
                        title = company.name_en if lang == "en" else company.name_cn
                    else:
                        graph = await DatasetGraphService(session).get(
                            owner, dataset_id, company_id, depth
                        )
                        title = graph["nodes"][0]["label"]
                    reference = CompanyGraphReference(
                        companyId=company_id,
                        depth=depth,
                        lang=lang,
                        title=title,
                        datasetId=graph["datasetId"],
                        datasetName=graph["datasetName"],
                        snapshot=graph["snapshot"],
                        demo=graph["demo"],
                        truncated=graph["truncated"],
                        truncationReasons=graph["truncationReasons"],
                        summary=GraphSummary(
                            nodeCount=len(graph["nodes"]), edgeCount=len(graph["edges"])
                        ),
                    )
                    return {
                        "status": "success",
                        "content": [{"json": reference.model_dump(mode="json")}],
                    }
            except AppError as exc:
                return failure(exc.code, exc.message)
            except Exception as exc:
                logger.warning(
                    "assistant.graph_lookup_failed", extra={"cause_type": type(exc).__name__}
                )
                return failure("GRAPH_UNAVAILABLE", "Graph lookup is unavailable")

        return [search_companies, show_company_graph]
