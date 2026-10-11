from pathlib import Path

from riskgnn.dataset_adapters.analysis.singapore import analyze
from riskgnn.dataset_adapters.archive import data_root
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.sg_comrisk.preparation import prepare
from riskgnn.dataset_adapters.sg_comrisk.validation import validate


class SingaporeAdapter(DatasetAdapter):
    id = "sg-comrisk"
    version = "1"
    trainable = True

    def inspect(self, archive: Path, workspace: Path, config: dict) -> dict:
        if config:
            raise ValueError("sg-comrisk v1 does not accept additional configuration")
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
        if config:
            raise ValueError("sg-comrisk v1 does not accept additional configuration")
        return prepare(validated, output)
