from typing import Any

from risk_api.modules.company.service import CompanyService
from risk_api.modules.graph.errors import GraphNotFound
from risk_api.modules.graph.repository import GraphRepository


class GraphService:
    def __init__(self, companies: CompanyService, repository: GraphRepository):
        self.companies = companies
        self.repository = repository

    async def get(self, company_id: str, lang: str, depth: int) -> dict[str, Any]:
        await self.companies.get_model(company_id)
        data = await self.repository.get(company_id, lang, depth)
        if data is None:
            raise GraphNotFound()
        return data
