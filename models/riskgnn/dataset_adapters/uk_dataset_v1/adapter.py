from collections.abc import Iterable
from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult
from riskgnn.dataset_adapters.delivery import delivery_for
from riskgnn.dataset_adapters.enterprise import snapshot_records
from riskgnn.dataset_adapters.snapshot_io import load, verified
from riskgnn.dataset_adapters.uk_dataset_v1.analysis import analyze
from riskgnn.dataset_adapters.uk_dataset_v1.preparation import prepare
from riskgnn.dataset_adapters.uk_dataset_v1.validation import validate


class UKAdapter(DatasetAdapter):
    id = "uk-dataset-v1"
    version = "2"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        delivery_for(self.id, self.version).config(config)
        result = validate(archive, workspace)
        result["analysis"] = analyze(workspace / result["root"], result)
        result["limitations"] = [
            "12-month formal insolvency in a matched research cohort, not population default risk",
            "Current registry approximates historical observations; historical graph unverified",
            "Observation IDs are model identities; company IDs remain source metadata",
        ]
        result.pop("datasetContract", None)
        return InspectionResult.model_validate(result)

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        resolved = delivery_for(self.id, self.version).config(config)
        return prepare(validated, output, int(resolved["target_count"]))

    def enterprise_records(self, validated: Path) -> Iterable[EnterpriseRecord]:
        _, root = verified(validated, "uk-research-v2")
        yield from snapshot_records(load(root))
