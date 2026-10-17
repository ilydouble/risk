"""Display names survive snapshot validation and enterprise export."""

import json

import pytest

from riskgnn.dataset_adapters.enterprise import snapshot_records
from riskgnn.dataset_adapters.snapshot_io import load


@pytest.mark.parametrize("name", [None, "EXAMPLE UK LIMITED"])
def test_snapshot_names_survive_export(tmp_path, name):
    for split in ("train", "valid", "test"):
        company = {
            "id": "00805326", "kind": "company", "community": "test",
            "features": [1.0], "label": 0, "split": split,
        }
        if name is not None:
            company["name"] = name
            company["properties"] = {"nameSource": {"snapshotDate": "2026-09-30"}}
        snapshot = {
            "schema_version": 1, "name": split, "synthetic": False,
            "evaluation": "isolated_snapshots", "target_description": "test status",
            "feature_names": ["value"], "relation_names": ["test"],
            "hyperedge_types": ["test"], "nodes": [company],
            "edges": [], "hyperedges": [], "events": [],
        }
        (tmp_path / f"{split}.json").write_text(json.dumps(snapshot))
    records = list(snapshot_records(load(tmp_path)))
    assert len(records) == 3
    assert all(row.nodeId == "00805326" and row.data["name"] == name for row in records)
    assert all(row.data["attributes"] == {"value": 1.0} for row in records)
    expected = {"nameSource": {"snapshotDate": "2026-09-30"}} if name else {}
    assert all(row.data["properties"] == expected for row in records)
