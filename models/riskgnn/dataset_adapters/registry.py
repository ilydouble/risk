from pathlib import Path

from riskgnn.dataset_adapters.acra.adapter import SingaporeAdapter
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult, ValidatedDataset
from riskgnn.dataset_adapters.smesd.adapter import SMEsDAdapter
from riskgnn.dataset_adapters.uk_dataset_v1.adapter import UKAdapter
from riskgnn.dataset_adapters.uk_dataset_v1.legacy import LegacyUKAdapter
from riskgnn.workbench.artifacts import digest, write_json

_ADAPTERS: dict[tuple[str, str], DatasetAdapter] = {
    (adapter.id, adapter.version): adapter
    for adapter in (SingaporeAdapter(), SMEsDAdapter(), UKAdapter(), LegacyUKAdapter())
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
    if not isinstance(result, InspectionResult):
        raise TypeError("Adapter.inspect must return InspectionResult")
    if result.sha256 != digest(source):
        raise ValueError("Inspection source SHA-256 does not match the uploaded ZIP")
    validated = ValidatedDataset.model_validate(
        {
            **result.model_dump(mode="python", exclude_unset=True),
            "datasetContract": contract,
            "supportedRunnerIds": ["riskgnn"] if adapter.trainable else [],
            "compatibility": "compatible" if adapter.trainable else "incompatible",
            "issues": []
            if adapter.trainable
            else [
                {
                    "code": "DATASET_ANALYSIS_ONLY",
                    "message": "Dataset supports analysis only",
                }
            ],
        }
    )
    result_data = validated.model_dump(mode="json", exclude_unset=True)
    write_json(output / "validation.json", result_data)
    return result_data
