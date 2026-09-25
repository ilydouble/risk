from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class DocumentError(AppError):
    _cases = {
        "FILENAME_INVALID": (400, "Invalid filename"),
        "STORAGE_UNAVAILABLE": (503, "Storage unavailable"),
        "NOT_FOUND": (404, "Document not found"),
        "UPLOAD_INCOMPLETE": (409, "Upload not complete"),
        "SIZE_MISMATCH": (409, "Upload size mismatch"),
    }

    def __init__(self, kind: str):
        status, message = self._cases[kind]
        super().__init__(status, f"DOCUMENT_{kind}", message)


FILENAME_INVALID_RESPONSE: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope[Literal[400], Literal["DOCUMENT_FILENAME_INVALID"]]}
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["DOCUMENT_NOT_FOUND"]]}
}
UPLOAD_CONFLICT_RESPONSE: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorEnvelope[Literal[409], Literal["DOCUMENT_UPLOAD_INCOMPLETE"]]
        | ErrorEnvelope[Literal[409], Literal["DOCUMENT_SIZE_MISMATCH"]]
    }
}
STORAGE_UNAVAILABLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    503: {
        "model": ErrorEnvelope[Literal[503], Literal["AUTH_STORE_UNAVAILABLE"]]
        | ErrorEnvelope[Literal[503], Literal["AUTH_STORE_INVALID"]]
        | ErrorEnvelope[Literal[503], Literal["DOCUMENT_STORAGE_UNAVAILABLE"]]
    }
}
