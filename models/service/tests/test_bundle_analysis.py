from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from service.analysis.bundle import _psi, analyze_bundle
from service.datasets.bundle.data import DataValidationError, load_bundle
from service.tools.bundle_demo import build_demo_bundle


def test_numeric_psi_handles_interval_bins_and_values_outside_training_range() -> None:
    train = pd.Series(range(100), dtype=float)
    assert _psi(train, train) == pytest.approx(0)
    shifted = pd.Series([*range(90), *([1000] * 10)], dtype=float)
    assert _psi(train, shifted) > 0


def test_analysis_uses_declared_splits_without_raw_preview(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "loan.zip", rows=180)

    data = load_bundle(path)
    analysis = analyze_bundle(data)

    assert analysis["excludedRawPreview"] is True
    assert analysis["quality"]["rowCount"] == 180
    assert analysis["quality"]["duplicateRows"] == 0
    assert set(analysis["splits"]) == {"train", "validation", "test"}
    assert {item["name"] for item in analysis["signals"]} == {
        "debt_ratio",
        "overdue_count",
        "company_age_years",
        "industry",
    }
    assert data.capabilities["tabular"] is True
    assert data.capabilities["gnn"] is False


def test_graph_analysis_reports_components(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "graph.zip", rows=180, include_graph=True)

    analysis = analyze_bundle(load_bundle(path))

    assert analysis["graph"]["available"] is True
    assert analysis["graph"]["connectedComponents"] == 3
    assert analysis["graph"]["relationTypes"]


def test_sample_contract_rejects_invalid_split(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "entity.zip", "entity_snapshot")
    with zipfile.ZipFile(path) as source:
        metadata = json.loads(source.read("metadata.json"))
        samples = source.read("samples.csv").replace(b",train,", b",future,", 1)
    metadata["files"]["samples"]["sizeBytes"] = len(samples)
    metadata["files"]["samples"]["sha256"] = hashlib.sha256(samples).hexdigest()
    invalid = io.BytesIO()
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("samples.csv", samples)

    with pytest.raises(DataValidationError, match="split"):
        load_bundle(invalid.getvalue())


def test_parquet_samples_are_supported(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "source.zip")
    with zipfile.ZipFile(path) as source:
        metadata = json.loads(source.read("metadata.json"))
        samples = pd.read_csv(io.BytesIO(source.read("samples.csv")))
    parquet = io.BytesIO()
    samples.to_parquet(parquet, index=False)
    payload = parquet.getvalue()
    metadata["files"]["samples"] = {
        "path": "samples.parquet",
        "format": "parquet",
        "sizeBytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("samples.parquet", payload)

    data = load_bundle(bundle.getvalue())

    assert len(data.samples) == 180
