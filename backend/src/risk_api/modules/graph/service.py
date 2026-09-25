from risk_api.modules.company.service import CompanyService
from risk_api.modules.graph.errors import GraphNotFound
from risk_api.modules.graph.repository import GraphRepository
from risk_api.schemas import GraphData, ResponseGetGraph


class GraphService:
    def __init__(self, companies: CompanyService, repository: GraphRepository):
        self.companies = companies
        self.repository = repository

    async def get(self, company_id: str, lang: str, depth: int) -> ResponseGetGraph:
        await self.companies.get_model(company_id)
        data = await self.repository.get(company_id, lang, depth)
        if data is None:
            raise GraphNotFound()
        return ResponseGetGraph(graph=GraphData.model_validate(data))
