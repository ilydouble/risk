from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workbench.worker import Job, ModelingWorker


async def run_experiment(worker: ModelingWorker, job: Job) -> None:
    """Implemented by the model-ladder stage; kept explicit to fail retryably meanwhile."""
    _ = worker, job
    raise RuntimeError("model ladder is not installed yet")
