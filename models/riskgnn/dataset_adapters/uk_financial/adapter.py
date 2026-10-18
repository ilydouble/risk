from collections.abc import Iterable
from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult
from riskgnn.dataset_adapters.uk_financial.readers import json_rows
from riskgnn.dataset_adapters.uk_financial.validation import NORMALIZED, validate


class FinancialAdapter(DatasetAdapter):
    id = "uk-financial-jsonl"
    version = "1"
    trainable = False

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        return validate(archive, workspace, config)

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        raise ValueError(
            "Financial observations are for deployed-model inference, not GNN training"
        )

    def enterprise_records(self, validated: Path) -> Iterable[EnterpriseRecord]:
        for _, row in json_rows(validated / NORMALIZED):
            yield EnterpriseRecord.model_validate(row)
