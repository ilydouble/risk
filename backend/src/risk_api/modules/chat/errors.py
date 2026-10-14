from typing import Any, Literal

from risk_api.shared.api.envelope import ErrorEnvelope

CHAT_ERRORS: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorEnvelope[Literal[503], Literal["CHAT_NOT_CONFIGURED", "CHAT_UNREACHABLE"]]},
    504: {"model": ErrorEnvelope[Literal[504], Literal["CHAT_TIMEOUT"]]},
    502: {
        "model": ErrorEnvelope[
            Literal[502],
            Literal["CHAT_AUTH_FAILED", "CHAT_UPSTREAM_ERROR", "CHAT_INVALID_RESPONSE"],
        ]
    },
}
