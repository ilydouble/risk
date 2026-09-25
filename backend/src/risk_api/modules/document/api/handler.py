from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.document.api.schemas import (
    DocumentDTO,
    RequestCompleteUpload,
    RequestCreateDownload,
    RequestCreateUpload,
    RequestListDocuments,
    ResponseCompleteUpload,
    ResponseCreateDownload,
    ResponseCreateUpload,
    ResponseListDocuments,
)
from risk_api.modules.document.model import Document
from risk_api.modules.document.service import DocumentService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success


def to_dto(document: Document) -> DocumentDTO:
    return DocumentDTO(
        id=document.id,
        companyId=document.company_id,
        filename=document.filename,
        contentType=document.content_type,
        size=document.size,
        createdAt=document.created_at.isoformat() if document.created_at else "",
    )


async def create_upload(
    body: RequestCreateUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCreateUpload]:
    await authorize_request(request, auth)
    ticket = await service.create_upload(body.companyId, body.filename, body.contentType, body.size)
    return success(
        ResponseCreateUpload(documentId=ticket.document_id, url=ticket.url, headers=ticket.headers)
    )


async def complete_upload(
    body: RequestCompleteUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCompleteUpload]:
    await authorize_request(request, auth)
    document = await service.complete(body.documentId)
    return success(ResponseCompleteUpload(document=to_dto(document)))


async def list_documents(
    body: RequestListDocuments,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseListDocuments]:
    await authorize_request(request, auth)
    documents = await service.list(body.companyId)
    return success(ResponseListDocuments(items=[to_dto(document) for document in documents]))


async def create_download(
    body: RequestCreateDownload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCreateDownload]:
    await authorize_request(request, auth)
    url = await service.create_download(body.documentId)
    return success(ResponseCreateDownload(url=url))
