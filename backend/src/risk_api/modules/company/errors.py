from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class CompanyNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "COMPANY_NOT_FOUND", "Company not found")


NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["COMPANY_NOT_FOUND"]]}
}
