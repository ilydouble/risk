from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path


class DatasetAdapter(ABC):
    """Data semantics belong to the model; the service never calls these methods."""

    id: str
    version: str
    trainable: bool

    @abstractmethod
    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        """Validate and describe data according to this adapter's own semantics."""

    @abstractmethod
    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        """Load, split and encode model inputs; output layout is model-owned."""

    def enterprise_records(self, validated: Path) -> Iterable[dict]:
        """Export readable data; concrete adapters own the source mapping."""
        raise NotImplementedError("This adapter does not export enterprise data")
