from typing import Any, Literal

from risk_api.shared.api.envelope import ErrorEnvelope

DATA_PREP_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["DATA_PREP_NOT_FOUND"]]},
    422: {
        "model": ErrorEnvelope[
            Literal[422],
            Literal[
                "DATA_PREP_SIZE_INVALID",
                "DATA_PREP_ENCODING_INVALID",
                "DATA_PREP_HEADER_INVALID",
                "DATA_PREP_HEADER_DUPLICATE",
                "DATA_PREP_ROW_INVALID",
                "DATA_PREP_ROWS_EXCEEDED",
                "DATA_PREP_EMPTY",
                "DATA_PREP_FORMAT_UNSUPPORTED",
                "DATA_PREP_CONTENT_INVALID",
                "DATA_PREP_MAPPING_INVALID",
            ],
        ]
    },
    502: {
        "model": ErrorEnvelope[
            Literal[502],
            Literal[
                "DATA_PREP_SUGGESTION_INVALID",
                "CHAT_AUTH_FAILED",
                "CHAT_UPSTREAM_ERROR",
                "CHAT_INVALID_RESPONSE",
            ],
        ]
    },
    503: {"model": ErrorEnvelope[Literal[503], Literal["CHAT_NOT_CONFIGURED", "CHAT_UNREACHABLE"]]},
    504: {"model": ErrorEnvelope[Literal[504], Literal["CHAT_TIMEOUT"]]},
}
