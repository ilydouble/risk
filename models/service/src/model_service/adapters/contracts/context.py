from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .errors import AdapterCancelled
from .events import AdapterEvent


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    attempt_id: str
    request_id: str
    work_dir: Path
    output_dir: Path
    emit_event: Callable[[AdapterEvent], None]
    is_cancelled: Callable[[], bool] = lambda: False
    device: str = "cpu"
    resources: dict[str, int] = field(default_factory=dict)

    def check_cancelled(self) -> None:
        if self.is_cancelled():
            raise AdapterCancelled()

    def emit(self, event: AdapterEvent) -> None:
        self.check_cancelled()
        self.emit_event(event)
