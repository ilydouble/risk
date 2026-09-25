from risk_api.modules.company.errors import CompanyNotFound
from risk_api.modules.company.model import Company
from risk_api.modules.company.query import CompanySearchQuery
from risk_api.modules.company.repository import CompanyRepository


class CompanyService:
    def __init__(self, repository: CompanyRepository):
        self.repository = repository

    async def get_model(self, company_id: str) -> Company:
        company = await self.repository.by_id(company_id)
        if company is None:
            raise CompanyNotFound()
        return company

    async def search(self, query: CompanySearchQuery) -> tuple[list[Company], int]:
        return await self.repository.search(query)
