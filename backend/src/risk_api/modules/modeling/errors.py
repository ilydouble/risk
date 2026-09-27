from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class ModelingError(AppError):
    _errors = {
        "DATASET_NOT_FOUND": (404, "MODELING_DATASET_NOT_FOUND", "Dataset not found"),
        "EXPERIMENT_NOT_FOUND": (404, "MODELING_EXPERIMENT_NOT_FOUND", "Experiment not found"),
        "FILE_INVALID": (422, "MODELING_FILE_INVALID", "Dataset bundle is invalid"),
        "CONFIGURATION_INVALID": (
            422,
            "MODELING_CONFIGURATION_INVALID",
            "Experiment configuration is invalid",
        ),
        "UPLOAD_INCOMPLETE": (409, "MODELING_UPLOAD_INCOMPLETE", "Dataset upload is incomplete"),
        "DATASET_NOT_READY": (409, "MODELING_DATASET_NOT_READY", "Dataset is not ready"),
        "STORAGE_UNAVAILABLE": (503, "MODELING_STORAGE_UNAVAILABLE", "Storage is unavailable"),
    }

    def __init__(self, kind: str, *, field: str | None = None):
        status, code, message = self._errors[kind]
        super().__init__(status, code, message, field=field)


ErrorResponses = dict[int | str, dict[str, Any]]

DATASET_NOT_FOUND_RESPONSE: ErrorResponses = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["MODELING_DATASET_NOT_FOUND"]]}
}
EXPERIMENT_NOT_FOUND_RESPONSE: ErrorResponses = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["MODELING_EXPERIMENT_NOT_FOUND"]]}
}
FILE_INVALID_RESPONSE: ErrorResponses = {
    422: {"model": ErrorEnvelope[Literal[422], Literal["MODELING_FILE_INVALID"]]}
}
CONFIGURATION_INVALID_RESPONSE: ErrorResponses = {
    422: {"model": ErrorEnvelope[Literal[422], Literal["MODELING_CONFIGURATION_INVALID"]]}
}
UPLOAD_INCOMPLETE_RESPONSE: ErrorResponses = {
    409: {"model": ErrorEnvelope[Literal[409], Literal["MODELING_UPLOAD_INCOMPLETE"]]}
}
DATASET_NOT_READY_RESPONSE: ErrorResponses = {
    409: {"model": ErrorEnvelope[Literal[409], Literal["MODELING_DATASET_NOT_READY"]]}
}
STORAGE_UNAVAILABLE_RESPONSE: ErrorResponses = {
    503: {"model": ErrorEnvelope[Literal[503], Literal["MODELING_STORAGE_UNAVAILABLE"]]}
}
