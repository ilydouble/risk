from typing import Any, Literal

from risk_api.errors import AppError
from risk_api.shared.api.envelope import ErrorEnvelope


class BenchmarkNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "BENCHMARK_COMPANY_NOT_FOUND", "Benchmark company not found")


class BenchmarkUnavailable(AppError):
    def __init__(self) -> None:
        super().__init__(503, "BENCHMARK_MODEL_UNAVAILABLE", "Benchmark model unavailable")


BENCHMARK_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope[Literal[404], Literal["BENCHMARK_COMPANY_NOT_FOUND"]]},
    503: {"model": ErrorEnvelope[Literal[503], Literal["BENCHMARK_MODEL_UNAVAILABLE"]]},
}
