from pathlib import Path

from riskgnn.dataset_adapters.snapshot_io import validate as validate_snapshots
from riskgnn.dataset_adapters.uk_dataset_v1.schemas import check
from riskgnn.workbench.artifacts import digest, read_json


def validate(source: Path, destination: Path) -> dict:
    result = validate_snapshots(source, destination, "uk-dataset-v1", check)
    root = destination / result["root"]
    for name in ("audit.json", "export_meta.json"):
        metadata = read_json(root / name)
        for split in ("train", "valid", "test"):
            expected = metadata["snapshots"][split]["sha256"]
            if digest(root / f"{split}.json") != expected:
                raise ValueError(f"UK snapshot SHA-256 does not match {name}: {split}")
    return result
