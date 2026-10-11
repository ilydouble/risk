from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.smesd.analysis import analyze
from riskgnn.dataset_adapters.smesd.preparation import prepare
from riskgnn.dataset_adapters.smesd.validation import validate
from riskgnn.dataset_adapters.snapshot_preparation import target_count


class SMEsDAdapter(DatasetAdapter):
    id = "smesd"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        target_count(config, 4000)
        result = validate(archive, workspace)
        result["analysis"] = analyze(workspace / result["root"], result)
        result["limitations"] = [
            "Static status classification, not forward default probability",
            "node_edge uses company/person nodes and directed weighted edges; "
            "hyperedges and events are retained evidence only",
        ]
        return result

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        return prepare(validated, output, target_count(config, 4000))
