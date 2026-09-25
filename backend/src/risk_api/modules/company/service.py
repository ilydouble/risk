from risk_api.models import Company
from risk_api.modules.company.errors import CompanyNotFound
from risk_api.modules.company.repository import CompanyRepository
from risk_api.schemas import (
    CompanyDTO,
    CompanyProfile,
    RequestSearchCompany,
    ResponseGetCompany,
    ResponseSearchCompany,
)


class CompanyService:
    def __init__(self, repository: CompanyRepository):
        self.repository = repository

    async def get_model(self, company_id: str) -> Company:
        company = await self.repository.by_id(company_id)
        if company is None:
            raise CompanyNotFound()
        return company

    async def get(self, company_id: str) -> ResponseGetCompany:
        company = await self.get_model(company_id)
        return ResponseGetCompany(
            company=CompanyDTO.model_validate(company.summary),
            profile=CompanyProfile.model_validate(company.profile),
        )

    async def search(self, query: RequestSearchCompany) -> ResponseSearchCompany:
        companies, total = await self.repository.search(query)
        return ResponseSearchCompany(
            items=[CompanyDTO.model_validate(company.summary) for company in companies],
            total=total,
            page=query.page,
            pageSize=query.pageSize,
        )
