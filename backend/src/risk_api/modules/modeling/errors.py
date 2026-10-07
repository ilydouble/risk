from typing import Literal

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.shared.api.envelope import ErrorEnvelope

WORKBENCH_ERRORS = {
    **SESSION_ERRORS,
    404: {
        "model": ErrorEnvelope[
            Literal[404], Literal["MODELING_RESOURCE_NOT_FOUND", "MODEL_RESOURCE_NOT_FOUND"]
        ]
    },
    409: {
        "model": ErrorEnvelope[
            Literal[409],
            Literal[
                "MODELING_STATE_INVALID",
                "MODELING_DATASET_NOT_READY",
                "MODELING_UPLOAD_INCOMPLETE",
                "MODEL_STATE_INVALID",
            ],
        ]
    },
    422: {
        "model": ErrorEnvelope[
            Literal[422],
            Literal["REQUEST_INVALID", "MODELING_FILE_INVALID", "MODELING_MODEL_INCOMPATIBLE"],
        ]
    },
    503: {
        "model": ErrorEnvelope[
            Literal[503], Literal["MODEL_SERVICE_UNAVAILABLE", "MODELING_STORAGE_UNAVAILABLE"]
        ]
    },
}
