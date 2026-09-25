from pathlib import PurePath
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient, NotFoundError, StorageError

from risk_api.models import Document
from risk_api.modules.company.service import CompanyService
from risk_api.modules.document.errors import DocumentError
from risk_api.modules.document.repository import DocumentRepository
from risk_api.schemas import (
    DocumentDTO,
    RequestCreateUpload,
    ResponseCompleteUpload,
    ResponseCreateDownload,
    ResponseCreateUpload,
    ResponseListDocuments,
)


def to_dto(document: Document) -> DocumentDTO:
    return DocumentDTO(
        id=document.id,
        companyId=document.company_id,
        filename=document.filename,
        contentType=document.content_type,
        size=document.size,
        createdAt=document.created_at.isoformat() if document.created_at else "",
    )


class DocumentService:
    def __init__(
        self, companies: CompanyService, repository: DocumentRepository, storage: AsyncClient
    ):
        self.companies = companies
        self.repository = repository
        self.storage = storage

    async def create_upload(self, body: RequestCreateUpload) -> ResponseCreateUpload:
        await self.companies.get_model(body.companyId)
        filename = PurePath(body.filename.replace("\\", "/")).name
        if filename in {"", ".", ".."}:
            raise DocumentError("FILENAME_INVALID")
        document_id = str(uuid4())
        key = f"companies/{body.companyId}/{document_id}/{filename}"
        try:
            signed = await self.storage.presign_put(
                key, size=body.size, content_type=body.contentType, expires_in=60
            )
        except StorageError as error:
            raise DocumentError("STORAGE_UNAVAILABLE") from error
        document = Document(
            id=document_id,
            company_id=body.companyId,
            object_key=key,
            filename=filename,
            content_type=body.contentType,
            size=body.size,
            status="pending",
        )
        await self.repository.add(document)
        return ResponseCreateUpload(
            documentId=document_id, url=signed.url, headers=dict(signed.headers)
        )

    async def complete(self, document_id: str) -> ResponseCompleteUpload:
        document = await self.repository.by_id(document_id)
        if document is None:
            raise DocumentError("NOT_FOUND")
        try:
            info = await self.storage.stat(document.object_key)
        except NotFoundError as error:
            raise DocumentError("UPLOAD_INCOMPLETE") from error
        except StorageError as error:
            raise DocumentError("STORAGE_UNAVAILABLE") from error
        if info.size != document.size:
            raise DocumentError("SIZE_MISMATCH")
        if document.status != "ready":
            await self.repository.complete(document)
        return ResponseCompleteUpload(document=to_dto(document))

    async def list(self, company_id: str) -> ResponseListDocuments:
        await self.companies.get_model(company_id)
        return ResponseListDocuments(
            items=[to_dto(row) for row in await self.repository.ready_for_company(company_id)]
        )

    async def create_download(self, document_id: str) -> ResponseCreateDownload:
        document = await self.repository.by_id(document_id)
        if document is None or document.status != "ready":
            raise DocumentError("NOT_FOUND")
        try:
            signed = await self.storage.presign_get(document.object_key, expires_in=60)
        except StorageError as error:
            raise DocumentError("STORAGE_UNAVAILABLE") from error
        return ResponseCreateDownload(url=signed.url)
