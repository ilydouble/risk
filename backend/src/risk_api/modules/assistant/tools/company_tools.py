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
from risk_api.modules.graph.repository import GraphRepository
from risk_api.modules.graph.service import GraphService

logger = logging.getLogger(__name__)


def failure(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}


class CompanyGraphTools:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], driver: AsyncDriver):
        self.sessions = sessions
        self.driver = driver

    def build(self, lang: Literal["zh", "en"]) -> list[AgentTool]:
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
        async def show_company_graph(company_id: str, depth: int = 2) -> dict[str, Any]:
            """Show a demo relationship graph for a known company, not a real risk assessment.

            Args:
                company_id: Exact company ID from search_companies or an explicit user selection.
                depth: Number of hops, from 1 to 3; defaults to 2.
            """
            try:
                arguments = ShowCompanyGraphInput(company_id=company_id, depth=depth)
                company_id, depth = arguments.company_id, arguments.depth
            except ValidationError:
                return failure("INVALID_ARGUMENT", "Company ID and depth from 1 to 3 are required")
            try:
                # Agent tasks outlive the HTTP request and can run tools concurrently.
                # Never capture a request-scoped SQLAlchemy session in these closures.
                async with self.sessions() as session:
                    companies = CompanyService(CompanyRepository(session))
                    graph = await GraphService(companies, GraphRepository(self.driver)).get(
                        company_id, lang, depth
                    )
                    company = await companies.get_model(company_id)
                    reference = CompanyGraphReference(
                        companyId=company_id,
                        depth=depth,
                        lang=lang,
                        title=company.name_en if lang == "en" else company.name_cn,
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
