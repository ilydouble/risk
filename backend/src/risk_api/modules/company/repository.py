from typing import Any

from sqlalchemy import Float, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from risk_api.modules.company.model import Company
from risk_api.modules.company.query import CompanySearchQuery


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_id(self, company_id: str) -> Company | None:
        return await self.session.get(Company, company_id)

    async def search(self, query: CompanySearchQuery) -> tuple[list[Company], int]:
        statement = select(Company)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            statement = statement.where(
                or_(
                    Company.name_cn.ilike(pattern),
                    Company.name_en.ilike(pattern),
                    Company.reg_no.ilike(pattern),
                )
            )
        if query.region != "all":
            statement = statement.where(Company.region == query.region)
        if query.sector != "all":
            statement = statement.where(Company.sector == query.sector)
        if query.risks:
            statement = statement.where(Company.risk_level.in_(query.risks))
        total = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        order: ColumnElement[Any]
        if query.sort == "score_asc":
            order = Company.credit_score.asc()
        elif query.sort == "dp_desc":
            order = cast(Company.summary["defaultProb"].astext, Float).desc()
        elif query.sort == "recent":
            order = Company.summary["updatedAt"].astext.desc()
        else:
            order = Company.credit_score.desc()
        rows = await self.session.scalars(
            statement.order_by(order, Company.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(rows), total or 0
