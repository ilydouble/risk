from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class AuthError(AppError):
    _cases = {
        "INVALID_CREDENTIALS": (401, "Invalid credentials"),
        "SESSION_EXPIRED": (401, "Session expired"),
        "STORE_UNAVAILABLE": (503, "Session store unavailable"),
        "STORE_INVALID": (503, "Session store invalid"),
    }

    def __init__(self, kind: str):
        status, message = self._cases[kind]
        super().__init__(status, f"AUTH_{kind}", message)


SESSION_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope[Literal[401], Literal["AUTH_SESSION_EXPIRED"]]},
    503: {
        "model": ErrorEnvelope[Literal[503], Literal["AUTH_STORE_UNAVAILABLE"]]
        | ErrorEnvelope[Literal[503], Literal["AUTH_STORE_INVALID"]]
    },
}

LOGIN_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope[Literal[401], Literal["AUTH_INVALID_CREDENTIALS"]]},
    503: {"model": ErrorEnvelope[Literal[503], Literal["AUTH_STORE_UNAVAILABLE"]]},
}

LOGOUT_ERRORS: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorEnvelope[Literal[503], Literal["AUTH_STORE_UNAVAILABLE"]]},
}
