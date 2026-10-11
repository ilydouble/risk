from pathlib import Path

from riskgnn.dataset_adapters.snapshot_preparation import prepare as prepare_snapshots
from riskgnn.dataset_adapters.uk_dataset_v1.schemas import FEATURES


def prepare(validated: Path, output: Path, target_count: int = 2000) -> dict:
    return prepare_snapshots(
        validated, output, "uk-dataset-v1", target_count, log_features=tuple(FEATURES[1:])
    )
