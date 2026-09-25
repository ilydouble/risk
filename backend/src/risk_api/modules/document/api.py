from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.auth.service import AuthService
from risk_api.modules.company.errors import NOT_FOUND_RESPONSE as COMPANY_NOT_FOUND_RESPONSE
from risk_api.modules.document.errors import (
    FILENAME_INVALID_RESPONSE,
    STORAGE_UNAVAILABLE_RESPONSE,
    UPLOAD_CONFLICT_RESPONSE,
)
from risk_api.modules.document.errors import (
    NOT_FOUND_RESPONSE as DOCUMENT_NOT_FOUND_RESPONSE,
)
from risk_api.modules.document.service import DocumentService
from risk_api.schemas import (
    COMMON_ERROR_RESPONSES,
    ApiEnvelope,
    RequestCompleteUpload,
    RequestCreateDownload,
    RequestCreateUpload,
    RequestListDocuments,
    ResponseCompleteUpload,
    ResponseCreateDownload,
    ResponseCreateUpload,
    ResponseListDocuments,
)

router = APIRouter(route_class=DishkaRoute)


@router.post(
    "/create-upload", response_model=ApiEnvelope[ResponseCreateUpload],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | COMPANY_NOT_FOUND_RESPONSE
    | FILENAME_INVALID_RESPONSE | STORAGE_UNAVAILABLE_RESPONSE,
)
async def create_upload(
    body: RequestCreateUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCreateUpload]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200, internal_code="SUCCESS", message="OK", data=await service.create_upload(body)
    )


@router.post(
    "/complete-upload",
    response_model=ApiEnvelope[ResponseCompleteUpload],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DOCUMENT_NOT_FOUND_RESPONSE
    | UPLOAD_CONFLICT_RESPONSE | STORAGE_UNAVAILABLE_RESPONSE,
)
async def complete_upload(
    body: RequestCompleteUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCompleteUpload]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200,
        internal_code="SUCCESS",
        message="OK",
        data=await service.complete(body.documentId),
    )


@router.post(
    "/list", response_model=ApiEnvelope[ResponseListDocuments],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | COMPANY_NOT_FOUND_RESPONSE,
)
async def list_documents(
    body: RequestListDocuments,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseListDocuments]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200, internal_code="SUCCESS", message="OK", data=await service.list(body.companyId)
    )


@router.post(
    "/create-download",
    response_model=ApiEnvelope[ResponseCreateDownload],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DOCUMENT_NOT_FOUND_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
async def create_download(
    body: RequestCreateDownload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[DocumentService],
) -> ApiEnvelope[ResponseCreateDownload]:
    await auth.authorize(request)
    return ApiEnvelope(
        code=200,
        internal_code="SUCCESS",
        message="OK",
        data=await service.create_download(body.documentId),
    )
