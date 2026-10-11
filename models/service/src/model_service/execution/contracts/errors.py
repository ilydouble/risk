from pydantic import Field

from .common import Contract


class ErrorDetail(Contract):
    code: str = Field(min_length=1)
    message: str
    path: str | None = None
    retryable: bool = False


class ExecutionError(Exception):
    def __init__(
        self, code: str, message: str, *, path: str | None = None, retryable: bool = False
    ):
        super().__init__(message)
        self.detail = ErrorDetail(code=code, message=message, path=path, retryable=retryable)


class ExecutionCancelled(ExecutionError):
    def __init__(self):
        super().__init__("EXECUTION_CANCELLED", "Operation cancelled")
