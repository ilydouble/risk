from pathlib import Path

from riskgnn.dataset_adapters.smesd.schemas import check
from riskgnn.dataset_adapters.snapshot_io import validate as validate_snapshots


def validate(source: Path, destination: Path) -> dict:
    # audit.json records original Pickle hashes, not these converted JSON bytes.
    # The server manifest fingerprints the actual uploaded snapshot files.
    return validate_snapshots(source, destination, "smesd-json-v5", check)
