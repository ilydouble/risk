"""Deployment-owned adapter registrations; uploaded data never selects Python code."""

from model_service.adapters.contracts import AdapterError, AdapterSpec, ModelAdapter
from model_service.adapters.riskgnn.adapter import RiskGNNAdapter, RiskGNNNodeOnlyAdapter


class AdapterRegistry:
    def __init__(self, adapters: tuple[type[ModelAdapter], ...]):
        self._adapters: dict[tuple[str, str], type[ModelAdapter]] = {}
        for adapter in adapters:
            spec = adapter.describe()
            key = (spec.adapter_id, spec.adapter_version)
            if key in self._adapters:
                raise ValueError(f"Duplicate adapter: {key}")
            self._adapters[key] = adapter

    def get(self, adapter_id: str, version: str) -> type[ModelAdapter]:
        try:
            return self._adapters[(adapter_id, version)]
        except KeyError as error:
            raise AdapterError(
                "ADAPTER_NOT_AVAILABLE", f"Adapter not installed: {adapter_id}@{version}"
            ) from error

    def describe(self) -> list[AdapterSpec]:
        return [adapter.describe() for adapter in self._adapters.values()]


registry = AdapterRegistry((RiskGNNAdapter, RiskGNNNodeOnlyAdapter))
