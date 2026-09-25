from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_id(self, document_id: str) -> Document | None:
        return await self.session.get(Document, document_id)

    async def add(self, document: Document) -> None:
        self.session.add(document)
        await self.session.commit()

    async def ready_for_company(self, company_id: str) -> list[Document]:
        result = await self.session.scalars(
            select(Document)
            .where(Document.company_id == company_id, Document.status == "ready")
            .order_by(Document.created_at.desc())
        )
        return list(result)

    async def complete(self, document: Document) -> None:
        document.status = "ready"
        await self.session.commit()
