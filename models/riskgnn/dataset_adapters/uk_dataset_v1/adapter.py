from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.delivery import delivery_for
from riskgnn.dataset_adapters.uk_dataset_v1.analysis import analyze
from riskgnn.dataset_adapters.uk_dataset_v1.preparation import prepare
from riskgnn.dataset_adapters.uk_dataset_v1.validation import validate


class UKAdapter(DatasetAdapter):
    id = "uk-dataset-v1"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        delivery_for(self.id, self.version).config(config)
        result = validate(archive, workspace)
        result["analysis"] = analyze(workspace / result["root"], result)
        result["limitations"] = [
            "Static status classification, not forward default probability",
            "node_edge uses company/person nodes and directed weighted edges; "
            "hyperedges and events are retained evidence only",
        ]
        return result

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        resolved = delivery_for(self.id, self.version).config(config)
        return prepare(validated, output, int(resolved["target_count"]))
