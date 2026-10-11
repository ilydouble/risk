"""Company feature quality, frozen split balance and drift; persons are not samples."""

from pathlib import Path

from riskgnn.dataset_adapters.snapshot_analysis import analyze as analyze_snapshots


def analyze(root: Path, manifest: dict) -> dict:
    return analyze_snapshots(root, manifest)
