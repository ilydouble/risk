from pathlib import Path

from riskgnn.dataset_adapters.snapshot_preparation import prepare as prepare_snapshots


def prepare(validated: Path, output: Path, target_count: int = 4000) -> dict:
    return prepare_snapshots(validated, output, "smesd-json-v5", target_count, log_features=())
