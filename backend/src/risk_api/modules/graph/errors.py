from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.schemas import ErrorEnvelope


class GraphNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "GRAPH_NOT_FOUND", "Graph not found")


NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorEnvelope[Literal[404], Literal["COMPANY_NOT_FOUND"]]
        | ErrorEnvelope[Literal[404], Literal["GRAPH_NOT_FOUND"]]
    }
}
