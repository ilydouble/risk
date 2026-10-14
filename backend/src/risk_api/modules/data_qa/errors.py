from typing import Any, Literal

from risk_api.shared.api.envelope import ErrorEnvelope

DATA_QA_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["DATA_QA_SCOPE_NOT_FOUND"]]},
    422: {"model": ErrorEnvelope[Literal[422], Literal["REQUEST_INVALID", "DATA_QA_UNSUPPORTED"]]},
    502: {
        "model": ErrorEnvelope[
            Literal[502],
            Literal[
                "CHAT_AUTH_FAILED",
                "CHAT_UPSTREAM_ERROR",
                "CHAT_INVALID_RESPONSE",
                "DATA_QA_PLAN_INVALID",
            ],
        ]
    },
    503: {
        "model": ErrorEnvelope[
            Literal[503],
            Literal[
                "CHAT_NOT_CONFIGURED",
                "CHAT_UNREACHABLE",
                "DATA_QA_DATABASE_UNAVAILABLE",
                "DATA_QA_QUERY_FAILED",
            ],
        ]
    },
    504: {"model": ErrorEnvelope[Literal[504], Literal["CHAT_TIMEOUT", "DATA_QA_TIMEOUT"]]},
}
