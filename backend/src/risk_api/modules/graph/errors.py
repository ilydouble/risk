from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class GraphNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "GRAPH_NOT_FOUND", "Graph not found")


NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorEnvelope[Literal[404], Literal["COMPANY_NOT_FOUND"]]
        | ErrorEnvelope[Literal[404], Literal["GRAPH_NOT_FOUND"]]
    }
}


DATASET_GRAPH_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorEnvelope[
            Literal[404],
            Literal[
                "MODELING_RESOURCE_NOT_FOUND",
                "GRAPH_COMPANY_NOT_FOUND",
                "COMPANY_NOT_FOUND",
                "GRAPH_NOT_FOUND",
            ],
        ]
    },
    409: {
        "model": ErrorEnvelope[
            Literal[409], Literal["GRAPH_DATA_UNAVAILABLE", "GRAPH_DATA_INVALID"]
        ]
    },
    422: {"model": ErrorEnvelope[Literal[422], Literal["GRAPH_INPUT_INVALID"]]},
    503: {"model": ErrorEnvelope[Literal[503], Literal["GRAPH_QUERY_TIMEOUT"]]},
}
