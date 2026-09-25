import logging
from dataclasses import dataclass
from pathlib import PurePath
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient, NotFoundError, StorageError

from risk_api.modules.company.service import CompanyService
from risk_api.modules.document.errors import DocumentError
from risk_api.modules.document.model import Document
from risk_api.modules.document.repository import DocumentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadTicket:
    document_id: str
    url: str
    headers: dict[str, str]


class DocumentService:
    def __init__(
        self, companies: CompanyService, repository: DocumentRepository, storage: AsyncClient
    ):
        self.companies = companies
        self.repository = repository
        self.storage = storage

    async def create_upload(
        self, company_id: str, filename: str, content_type: str, size: int
    ) -> UploadTicket:
        await self.companies.get_model(company_id)
        filename = PurePath(filename.replace("\\", "/")).name
        if filename in {"", ".", ".."}:
            raise DocumentError("FILENAME_INVALID")
        document_id = str(uuid4())
        key = f"companies/{company_id}/{document_id}/{filename}"
        try:
            signed = await self.storage.presign_put(
                key, size=size, content_type=content_type, expires_in=60
            )
        except StorageError as error:
            raise DocumentError("STORAGE_UNAVAILABLE") from error
        document = Document(
            id=document_id,
            company_id=company_id,
            object_key=key,
            filename=filename,
            content_type=content_type,
            size=size,
            status="pending",
        )
        await self.repository.add(document)
        logger.info(
            "document.upload_requested",
            extra={"company_id": company_id, "document_id": document_id, "size_bytes": size},
        )
        return UploadTicket(document_id=document_id, url=signed.url, headers=dict(signed.headers))

    async def complete(self, document_id: str) -> Document:
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
            logger.info(
                "document.upload_completed",
                extra={"company_id": document.company_id, "document_id": document.id},
            )
        return document

    async def list(self, company_id: str) -> list[Document]:
        await self.companies.get_model(company_id)
        return await self.repository.ready_for_company(company_id)

    async def create_download(self, document_id: str) -> str:
        document = await self.repository.by_id(document_id)
        if document is None or document.status != "ready":
            raise DocumentError("NOT_FOUND")
        try:
            signed = await self.storage.presign_get(document.object_key, expires_in=60)
        except StorageError as error:
            raise DocumentError("STORAGE_UNAVAILABLE") from error
        logger.info("document.download_link_issued", extra={"document_id": document.id})
        return signed.url
