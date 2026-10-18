"""Research-script compatibility imports from the independent model package."""

from uk_decision_runtime.runtime import (
    RUNTIME_FILE,
    load_decision_model,
    restore_buffers,
    restore_runtime_buffers,
    save_runtime_buffers,
)

__all__ = [
    "RUNTIME_FILE",
    "load_decision_model",
    "restore_buffers",
    "restore_runtime_buffers",
    "save_runtime_buffers",
]
