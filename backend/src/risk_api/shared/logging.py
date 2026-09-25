"""Application-owned logging setup and request correlation."""

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TextIO

from stellarmesh_logging import JSONFormatter, PrettyFormatter

_request_id: ContextVar[str | None] = ContextVar("risk_request_id", default=None)
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class _ApplicationHandler(logging.StreamHandler):
    """Marks the handler owned by this application for safe reconfiguration."""


class _RuntimeRecordFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn supplies a terminal-formatted duplicate that is not useful in JSON output.
        if hasattr(record, "color_message"):
            del record.color_message
        request_id = _request_id.get()
        if request_id is not None and not hasattr(record, "request_id"):
            record.request_id = request_id
        return True


def configure_logging(
    level: str = "INFO",
    *,
    output_format: str = "json",
    stream: TextIO | None = None,
    capture_root: bool = False,
) -> None:
    """Own application/Uvicorn output; the Alembic CLI may also capture root output."""
    normalized = level.upper()
    if normalized not in _LEVELS:
        raise ValueError(f"Unsupported RISK_LOG_LEVEL: {level}")
    selected_format = output_format.lower()
    if selected_format not in {"json", "pretty"}:
        raise ValueError(f"Unsupported RISK_LOG_FORMAT: {output_format}")

    application_logger = logging.getLogger("risk_api")
    uvicorn_logger = logging.getLogger("uvicorn")
    root = logging.getLogger()
    for target in (application_logger, uvicorn_logger):
        for existing in tuple(target.handlers):
            if target is uvicorn_logger or isinstance(existing, _ApplicationHandler):
                target.removeHandler(existing)
                existing.close()
    for existing in tuple(root.handlers):
        if isinstance(existing, _ApplicationHandler):
            root.removeHandler(existing)
            existing.close()

    handler = _ApplicationHandler(stream if stream is not None else sys.stdout)
    formatter = JSONFormatter if selected_format == "json" else PrettyFormatter
    handler.setFormatter(formatter(static_fields={"service": "risk-backend"}))
    handler.addFilter(_RuntimeRecordFilter())
    application_logger.addHandler(handler)
    application_logger.setLevel(_LEVELS[normalized])
    application_logger.propagate = False

    uvicorn_logger.addHandler(handler)
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn_logger.propagate = False
    # Direct `uvicorn risk_api.main:app` installs child handlers before lifespan starts.
    uvicorn_error = logging.getLogger("uvicorn.error")
    for existing in tuple(uvicorn_error.handlers):
        uvicorn_error.removeHandler(existing)
        existing.close()
    uvicorn_error.setLevel(logging.NOTSET)
    uvicorn_error.propagate = True
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True

    if capture_root:
        # Alembic runs in a separate process; replace its text handler only there.
        for existing in tuple(root.handlers):
            root.removeHandler(existing)
            existing.close()
        root.addHandler(handler)
        root.setLevel(logging.INFO)


@contextmanager
def request_log_context(request_id: str) -> Iterator[None]:
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)
