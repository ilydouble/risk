from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.bundle.adapter import BundleAdapter
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.sg_comrisk.adapter import SingaporeAdapter
from riskgnn.workbench.artifacts import write_json

_ADAPTERS: dict[tuple[str, str], DatasetAdapter] = {
    (adapter.id, adapter.version): adapter for adapter in (SingaporeAdapter(), BundleAdapter())
}


def resolve(source: Path) -> tuple[DatasetAdapter, dict]:
    contract, _ = read_contract(source)
    identity = contract["adapter"]
    try:
        return _ADAPTERS[(identity["id"], identity["version"])], contract
    except KeyError as error:
        raise ValueError("Dataset adapter/version is not supported by this model") from error


def inspect(source: Path, output: Path) -> dict:
    adapter, contract = resolve(source)
    result = adapter.inspect(source, output, contract["adapter"]["config"])
    result["datasetContract"] = contract
    result["supportedRunnerIds"] = ["riskgnn"] if adapter.trainable else []
    result["compatibility"] = "compatible" if adapter.trainable else "incompatible"
    result["issues"] = (
        []
        if adapter.trainable
        else [
            {
                "code": "DATASET_ANALYSIS_ONLY",
                "message": "Dataset supports analysis only",
            }
        ]
    )
    write_json(output / "validation.json", result)
    return result
