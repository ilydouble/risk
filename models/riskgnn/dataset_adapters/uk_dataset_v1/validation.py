from pathlib import Path

from riskgnn.dataset_adapters.snapshot_io import validate as validate_snapshots
from riskgnn.dataset_adapters.uk_dataset_v1.schemas import check
from riskgnn.workbench.artifacts import digest, read_json


def validate_legacy(source: Path, destination: Path) -> dict:
    result = validate_snapshots(source, destination, "uk-dataset-v1", check)
    root = destination / result["root"]
    for name in ("audit.json", "export_meta.json"):
        metadata = read_json(root / name)
        for split in ("train", "valid", "test"):
            expected = metadata["snapshots"][split]["sha256"]
            if digest(root / f"{split}.json") != expected:
                raise ValueError(f"UK snapshot SHA-256 does not match {name}: {split}")
    return result


def validate(source: Path, destination: Path) -> dict:
    from riskgnn.dataset_adapters.uk_dataset_v1.research_schema import check

    def policy_check(snapshots):
        # The manifest and policy are extracted before the snapshot checker is invoked.
        from riskgnn.dataset_adapters.contract import read_contract

        _, relative = read_contract(source)
        root = destination / relative
        check(snapshots, read_json(root / "feature-policy.json"))

    result = validate_snapshots(source, destination, "uk-research-v2", policy_check)
    root = destination / result["root"]
    metadata = read_json(root / "export_meta.json")
    for split in ("train", "valid", "test"):
        for name in ("audit.json", "export_meta.json"):
            if (
                digest(root / f"{split}.json")
                != read_json(root / name)["snapshots"][split]["sha256"]
            ):
                raise ValueError("UK research snapshot digest mismatch")
    for name in ("feature-policy.json", "split-audit.csv"):
        if digest(root / name) != metadata["inputDigests"][name]:
            raise ValueError("UK research policy/audit digest mismatch")
    result["datasetProfile"]["taskType"] = "entity_observation"
    result["datasetProfile"]["metadata"] = metadata["researchAssumption"]
    return result
