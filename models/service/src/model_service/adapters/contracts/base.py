from abc import ABC, abstractmethod

from .context import ExecutionContext
from .io import OperationRequest, OperationResult
from .spec import AdapterSpec


class ModelAdapter(ABC):
    @classmethod
    @abstractmethod
    def describe(cls) -> AdapterSpec:
        """Return static capabilities without loading data, weights or accelerators."""

    @abstractmethod
    def execute(self, request: OperationRequest, context: ExecutionContext) -> OperationResult:
        """Run one operation; persist cross-operation state in declared artifacts."""
