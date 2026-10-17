"""Redelivery preserves training identities and refuses ambiguous source evidence."""

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "uk_redelivery", Path(__file__).resolve().parents[3] / "scripts/redeliver_uk_dataset.py"
)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def official_archive(tmp_path, rows):
    path = tmp_path / "names.zip"
    with ZipFile(path, "w") as zipped:
        zipped.writestr("names.csv", "CompanyName, CompanyNumber,CompanyStatus\n" + rows)
    return path


def test_name_evidence_does_not_change_training_inputs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    stats = {}
    original = {}
    for index, split in enumerate(pipeline.SPLITS):
        document = {
            "feature_names": ["value"],
            "relation_names": ["EQUITY"],
            "hyperedge_types": ["director_group"],
            "target_description": "legacy status",
            "nodes": [
                {
                    "id": f"0000000{index}",
                    "kind": "company",
                    "community": "test",
                    "features": [1.0],
                    "label": index % 2,
                    "split": split,
                }
            ],
            "edges": [],
            "hyperedges": [],
            "events": [],
        }
        original[split] = document
        path = source / f"{split}.json"
        pipeline.write_json(path, document)
        stats[split] = {"sha256": pipeline.digest(path)}
    for filename in ("audit.json", "export_meta.json"):
        pipeline.write_json(source / filename, {"snapshots": stats})
    names = official_archive(tmp_path, "EXAMPLE LIMITED,00000000,Active\n")
    output = tmp_path / "delivery"
    report = pipeline.redeliver(source, names, output, "test", "2026-09-30", "https://example")
    assert report["namesMatched"] == 1 and report["namesMissing"] == 2
    for split in pipeline.SPLITS:
        current = json.loads((output / "data" / f"{split}.json").read_bytes())
        assert pipeline.fingerprint(current) == pipeline.fingerprint(original[split])
        assert pipeline.digest(source / f"{split}.json") == stats[split]["sha256"]
    node = json.loads((output / "data/train.json").read_bytes())["nodes"][0]
    assert node["id"] == "00000000" and node["name"] == "EXAMPLE LIMITED"
    assert node["properties"]["nameSource"]["recordNumber"] == 2
    unnamed = json.loads((output / "data/test.json").read_bytes())["nodes"][0]
    assert unnamed["name"] is None


def test_conflicting_official_names_are_rejected(tmp_path):
    names = official_archive(
        tmp_path, "FIRST LIMITED,00000000,Active\nSECOND LIMITED,00000000,Active\n"
    )
    with pytest.raises(ValueError, match="Ambiguous"):
        pipeline.names_from_archive(names, {"00000000"})
