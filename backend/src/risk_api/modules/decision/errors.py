from typing import Literal

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.shared.api.envelope import ErrorEnvelope

DECISION_ERRORS = {
    **SESSION_ERRORS,
    404: {
        "model": ErrorEnvelope[
            Literal[404],
            Literal[
                "DECISION_RECORD_NOT_FOUND",
                "DECISION_PREDICTION_NOT_FOUND",
                "MODELING_RESOURCE_NOT_FOUND",
            ],
        ]
    },
    409: {
        "model": ErrorEnvelope[
            Literal[409],
            Literal[
                "DECISION_DATA_NOT_READY",
                "DECISION_REQUEST_CONFLICT",
                "DECISION_VERSION_CONFLICT",
                "DECISION_VERSION_CHANGED",
            ],
        ]
    },
    422: {
        "model": ErrorEnvelope[
            Literal[422],
            Literal[
                "REQUEST_INVALID",
                "DECISION_INPUT_INVALID",
                "DECISION_DATASET_UNSUPPORTED",
            ],
        ]
    },
    503: {
        "model": ErrorEnvelope[
            Literal[503],
            Literal[
                "MODEL_SERVICE_UNAVAILABLE",
                "DECISION_MODEL_DISABLED",
                "DECISION_MODEL_UNAVAILABLE",
                "DECISION_BUSY",
                "DECISION_TIMEOUT",
                "DECISION_PROTOCOL_INVALID",
                "DECISION_PREDICTION_FAILED",
                "AUTH_STORE_UNAVAILABLE",
                "AUTH_STORE_INVALID",
            ],
        ]
    },
}
