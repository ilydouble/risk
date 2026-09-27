from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from workbench.bundle import BundleLimits, BundleValidationError, validate_bundle
from workbench.demo import build_demo_bundle


def test_demo_bundle_satisfies_v1_contract(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "loan.zip")

    bundle = validate_bundle(path)

    assert bundle.metadata.task_type == "loan_application"
    assert bundle.metadata.target.name == "default_12m"
    assert bundle.metadata.capabilities() == {
        "tabular": True,
        "nodes": False,
        "relations": False,
        "events": False,
        "hyperedges": False,
        "gnn": False,
    }
    assert bundle.members == ("metadata.json", "samples.csv")


def test_bundle_rejects_hash_mismatch(tmp_path: Path) -> None:
    path = build_demo_bundle(tmp_path / "entity.zip", "entity_snapshot")
    with zipfile.ZipFile(path) as source:
        metadata = json.loads(source.read("metadata.json"))
        samples = source.read("samples.csv")
    metadata["files"]["samples"]["sha256"] = "0" * 64
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("samples.csv", samples)

    with pytest.raises(BundleValidationError, match="SHA-256"):
        validate_bundle(payload.getvalue())


def test_bundle_rejects_path_traversal() -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("metadata.json", "{}")
        archive.writestr("../samples.csv", "x")

    with pytest.raises(BundleValidationError, match="ZIP root"):
        validate_bundle(payload.getvalue())


def test_bundle_rejects_duplicate_member() -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("metadata.json", "{}")
        archive.writestr("metadata.json", "{}")

    with pytest.warns(UserWarning), pytest.raises(BundleValidationError, match="duplicate"):
        validate_bundle(payload.getvalue())


def test_bundle_rejects_compression_bomb_ratio() -> None:
    samples = b"a" * 100_000
    metadata = {
        "schemaVersion": 1,
        "datasetName": "bomb",
        "taskType": "entity_snapshot",
        "sampleUnit": "entity_snapshot",
        "columns": {
            "sampleId": "sample_id",
            "entityId": "entity_id",
            "observationTime": "observation_time",
            "graphSnapshotId": "graph_snapshot_id",
            "split": "split",
            "target": "target",
        },
        "target": {
            "name": "distress",
            "positiveValue": 1,
            "businessDefinition": "synthetic",
        },
        "features": [{"name": "x", "kind": "numeric", "group": "other"}],
        "files": {
            "samples": {
                "path": "samples.csv",
                "format": "csv",
                "sizeBytes": len(samples),
                "sha256": hashlib.sha256(samples).hexdigest(),
            }
        },
    }
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("samples.csv", samples)

    with pytest.raises(BundleValidationError, match="compression ratio"):
        validate_bundle(payload.getvalue(), BundleLimits(max_compression_ratio=5))
