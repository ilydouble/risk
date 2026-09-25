from typing import Any

from risk_api.models import Company
from risk_api.modules.company.service import CompanyService


class ScoreService:
    def __init__(self, companies: CompanyService):
        self.companies = companies

    async def get(self, company_id: str, lang: str) -> tuple[Company, dict[str, Any]]:
        company = await self.companies.get_model(company_id)
        return company, company.scores[lang]
