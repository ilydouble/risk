from risk_api.modules.company.service import CompanyService
from risk_api.schemas import CompanyDTO, ResponseGetScore, ScoreDetail


class ScoreService:
    def __init__(self, companies: CompanyService):
        self.companies = companies

    async def get(self, company_id: str, lang: str) -> ResponseGetScore:
        company = await self.companies.get_model(company_id)
        return ResponseGetScore(
            company=CompanyDTO.model_validate(company.summary),
            detail=ScoreDetail.model_validate(company.scores[lang]),
        )
