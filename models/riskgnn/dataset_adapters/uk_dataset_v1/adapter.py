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
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        delivery_for(self.id, self.version).config(config)
        result = validate(archive, workspace)
        result["analysis"] = analyze(workspace / result["root"], result)
        result["limitations"] = [
            "Static status classification, not forward default probability",
            "node_edge uses company/person nodes and directed weighted edges; "
            "hyperedges and events are retained evidence only",
        ]
        result.pop("datasetContract", None)
        return InspectionResult.model_validate(result)

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        resolved = delivery_for(self.id, self.version).config(config)
        return prepare(validated, output, int(resolved["target_count"]))

    def enterprise_records(self, validated: Path) -> Iterable[EnterpriseRecord]:
        _, root = verified(validated, "uk-dataset-v1")
        yield from snapshot_records(load(root))
