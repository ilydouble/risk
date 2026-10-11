from pathlib import Path

from riskgnn.dataset_adapters.acra.analysis import analyze
from riskgnn.dataset_adapters.acra.paths import data_root
from riskgnn.dataset_adapters.acra.preparation import prepare
from riskgnn.dataset_adapters.acra.validation import validate
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.snapshot_preparation import target_count


class SingaporeAdapter(DatasetAdapter):
    id = "sg-comrisk"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        target_count(config, 2000)
        _, relative = read_contract(archive)
        result = validate(archive, workspace)
        root = data_root(workspace)
        if root.resolve() != (workspace / relative).resolve():
            raise ValueError("Dataset files and contract must share the data root")
        result["analysis"] = analyze(root, result)
        result["datasetProfile"] = {
            "datasetFormat": "sg-comrisk-v1",
            "taskType": "entity_snapshot",
            "target": "Singapore corporate distress proxy",
            "features": result["features"],
            "splits": result["splits"],
            "relations": result["relations"],
        }
        return result

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        return prepare(validated, output, target_count=target_count(config, 2000))
