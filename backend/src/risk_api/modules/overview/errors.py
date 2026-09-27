from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class OverviewUnavailable(AppError):
    def __init__(self) -> None:
        super().__init__(503, "OVERVIEW_DATA_UNAVAILABLE", "Overview dataset is unavailable")


class OverviewCompanyNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "OVERVIEW_COMPANY_NOT_FOUND", "Overview company not found")


ErrorResponses = dict[int | str, dict[str, Any]]

UNAVAILABLE_RESPONSE: ErrorResponses = {
    503: {"model": ErrorEnvelope[Literal[503], Literal["OVERVIEW_DATA_UNAVAILABLE"]]}
}

NOT_FOUND_RESPONSE: ErrorResponses = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["OVERVIEW_COMPANY_NOT_FOUND"]]}
}
