from pathlib import Path

from riskgnn.dataset_adapters.snapshot_preparation import prepare as prepare_snapshots
from riskgnn.dataset_adapters.uk_dataset_v1.schemas import FEATURES


def prepare_legacy(validated: Path, output: Path, target_count: int = 2000) -> dict:
    return prepare_snapshots(
        validated, output, "uk-dataset-v1", target_count, log_features=tuple(FEATURES[1:])
    )


def prepare(validated: Path, output: Path, target_count: int = 2000) -> dict:
    from riskgnn.dataset_adapters.snapshot_io import verified
    from riskgnn.workbench.artifacts import read_json

    _, root = verified(validated, "uk-research-v2")
    policy = read_json(root / "feature-policy.json")
    return prepare_snapshots(
        validated,
        output,
        "uk-research-v2",
        target_count,
        signed_log_features=tuple(policy["signedLog1p"]),
    )
