from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.company.errors import NOT_FOUND_RESPONSE as COMPANY_NOT_FOUND_RESPONSE
from risk_api.modules.document.api import handler
from risk_api.modules.document.api.schemas import (
    ResponseCompleteUpload,
    ResponseCreateDownload,
    ResponseCreateUpload,
    ResponseListDocuments,
)
from risk_api.modules.document.errors import (
    FILENAME_INVALID_RESPONSE,
    STORAGE_UNAVAILABLE_RESPONSE,
    UPLOAD_CONFLICT_RESPONSE,
)
from risk_api.modules.document.errors import (
    NOT_FOUND_RESPONSE as DOCUMENT_NOT_FOUND_RESPONSE,
)
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/create-upload",
    handler.create_upload,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCreateUpload],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | COMPANY_NOT_FOUND_RESPONSE
    | FILENAME_INVALID_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
router.add_api_route(
    "/complete-upload",
    handler.complete_upload,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCompleteUpload],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | DOCUMENT_NOT_FOUND_RESPONSE
    | UPLOAD_CONFLICT_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
router.add_api_route(
    "/list",
    handler.list_documents,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseListDocuments],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | COMPANY_NOT_FOUND_RESPONSE,
)
router.add_api_route(
    "/create-download",
    handler.create_download,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCreateDownload],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | DOCUMENT_NOT_FOUND_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
