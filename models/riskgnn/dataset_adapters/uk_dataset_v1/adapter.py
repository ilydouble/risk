from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.snapshot_preparation import target_count
from riskgnn.dataset_adapters.uk_dataset_v1.analysis import analyze
from riskgnn.dataset_adapters.uk_dataset_v1.preparation import prepare
from riskgnn.dataset_adapters.uk_dataset_v1.validation import validate


class UKAdapter(DatasetAdapter):
    id = "uk-dataset-v1"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        target_count(config, 2000)
        result = validate(archive, workspace)
        result["analysis"] = analyze(workspace / result["root"], result)
        result["limitations"] = [
            "Static status classification, not forward default probability",
            "node_edge uses company/person nodes and directed weighted edges; "
            "hyperedges and events are retained evidence only",
        ]
        return result

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        return prepare(validated, output, target_count(config, 2000))
