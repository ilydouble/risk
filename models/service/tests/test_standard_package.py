import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from model_service.shared.dataset_contract import check_workbench_contract
from riskgnn.dataset_adapters.registry import inspect
from riskgnn.dataset_adapters.standard.contract import PROFILE
from riskgnn.workbench.artifacts import digest, read_json
from riskgnn.workbench_cli import execute


@pytest.fixture
def standard_package(tmp_path: Path):
    ids = [f"c:{i}" for i in range(12)]
    splits = ["train"] * 4 + ["valid"] * 4 + ["test"] * 4
    tables = {
        "entities": {"entity_id": ids, "kind": ["company"] * 12},
        "observations": {
            "sample_id": ids,
            "company_id": ids,
            "features": [[float(i)] * 18 for i in range(12)],
        },
        "labels": {"sample_id": ids, "label": [0, 1] * 6},
        "splits": {"sample_id": ids, "split": splits, "protocol": ["published"] * 12},
        "edges": {
            "source": ids,
            "target": ids[1:] + ids[:1],
            "relation": ["0"] * 12,
            "graph_view": ["investrelation"] * 12,
        },
        "audit_memberships": {"sample_id": ids},
    }
    task = {
        "dataset": {"id": "msgraphfin", "name": "MSGraphFin"},
        "featureNames": [f"F{i}" for i in range(18)],
    }
    files = {"task.json": json.dumps(task).encode()}
    for name, data in tables.items():
        buffer = pa.BufferOutputStream()
        pq.write_table(pa.table(data), buffer)
        files[f"{name}.parquet"] = buffer.getvalue().to_pybytes()
    descriptor = {
        "$schema": PROFILE,
        "name": "msgraphfin",
        "version": "1.0.0",
        "resources": [
            {"path": name, "hash": f"sha256:{hashlib.sha256(contents).hexdigest()}"}
            for name, contents in files.items()
        ],
    }
    files["datapackage.json"] = json.dumps(descriptor).encode()

    def build(*, tamper=False):
        archive = tmp_path / "data.zip"
        with ZipFile(archive, "w") as zipped:
            for name, contents in files.items():
                damaged = tamper and name == "task.json"
                zipped.writestr(name, contents + (b" " if damaged else b""))
        return archive

    return build


def test_standard_package_from_upload_to_evaluation(standard_package, tmp_path):
    archive = standard_package()
    check_workbench_contract(archive)
    asset = {"dataset": {"path": str(archive)}}

    def emit(_event):
        return None

    result = execute(
        {"operation": "inspect", "inputs": asset, "parameters": {}},
        tmp_path / "inspect",
        emit,
    )
    summary = result["data"]
    assert summary["sha256"] == digest(archive)
    assert summary["enterpriseData"]["counts"] == {"company": 12, "edge": 12}
    model = execute(
        {
            "operation": "train",
            "inputs": asset,
            "parameters": {"epochs": 1, "dataset": {"target_count": 12}},
        },
        tmp_path / "train",
        emit,
    )
    profile = model["data"]["profile"]
    assert profile["actualCounts"] == {"targets": 12, "train": 4, "validation": 4, "test": 4}
    assert profile["hyperedgeCount"] == 0
    assert profile["sourceSha256"] == digest(archive)
    assert "performance_status_audit" in profile["retainedOnlyInputs"]
    evaluation = execute(
        {
            "operation": "evaluate",
            "parameters": {},
            "inputs": {
                "model": {
                    "path": str(tmp_path / "train/output/model"),
                    "sha256": digest(archive),
                    "format": model["artifacts"]["model"]["format"],
                }
            },
        },
        tmp_path / "evaluate",
        emit,
    )
    assert evaluation["data"]["report"]["independentReload"]
    predictions = read_json(tmp_path / "evaluate/output/report/predictions.json")
    assert {row["companyId"] for row in predictions} == {f"c:{i}" for i in range(8, 12)}


def test_standard_package_rejects_changed_payload(standard_package, tmp_path):
    with pytest.raises(ValueError, match="checksum mismatch: task.json"):
        inspect(standard_package(tamper=True), tmp_path / "rejected")
