"""Adapter output boundaries, independent of dataset-specific training algorithms."""

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult, ValidatedDataset
from riskgnn.dataset_adapters.contracts.operation import InspectionOutput
from riskgnn.dataset_adapters.enterprise import export


@pytest.fixture
def inspection():
    return {
        "protocol": "example-v1", "sha256": "a" * 64,
        "files": [{"path": "source.json", "size": 1, "sha256": "b" * 64}],
        "counts": {"company_attr": 1}, "features": ["revenue"],
        "labeledCount": 1, "positiveCount": 0, "splits": [],
        "datasetProfile": {
            "datasetFormat": "example-v1", "taskType": "entity_snapshot", "target": "status",
        },
    }


@pytest.fixture
def validated(inspection):
    return {
        **inspection,
        "datasetContract": {
            "contract_version": 1, "dataset": {"id": "example", "version": "1"},
            "adapter": {"id": "example", "version": "1", "config": {}},
        },
        "supportedRunnerIds": ["riskgnn"], "compatibility": "compatible", "issues": [],
    }


def company():
    return EnterpriseRecord(
        kind="company", snapshot="test", nodeId="0001",
        data={"attributes": {"revenue": 1.5}, "label": 0, "name": None},
    )


class MissingExport(DatasetAdapter):
    def inspect(self, archive, workspace, config):
        raise NotImplementedError

    def prepare(self, validated, output, config):
        raise NotImplementedError


class ExportAdapter(MissingExport):
    def __init__(self, rows):
        self.rows = rows

    def enterprise_records(self, validated):
        yield from self.rows


def test_enterprise_export_is_required():
    with pytest.raises(TypeError):
        MissingExport()


@pytest.mark.parametrize("change", [
    {"sha256": "invalid"}, {"features": ["duplicate", "duplicate"]},
    {"counts": {"company_attr": -1}}, {"positiveCount": 2},
    {"datasetProfile": {"datasetFormat": "example-v1", "taskType": "entity_snapshot"}},
    {"files": [{"path": "../escape", "size": 1, "sha256": "b" * 64}]},
    {"metadata": {"nested": {"score": float("nan")}}}, {"typo": 1},
])
def test_inspection_rejects_incomplete_or_invalid_contract(inspection, change):
    with pytest.raises(ValidationError):
        InspectionResult.model_validate({**inspection, **change})


def test_typed_summary_preserves_explicit_extension_metadata(inspection, validated):
    result = InspectionResult.model_validate({**inspection, "metadata": {"source": "v1"}})
    assert result.metadata == {"source": "v1"}
    assert result.datasetProfile.target == "status"
    assert ValidatedDataset.model_validate(validated).datasetContract["dataset"]["id"] == "example"


@pytest.mark.parametrize("row", [
    {"kind": "unsupported", "snapshot": "s", "data": {}},
    {"kind": "company", "snapshot": "s", "nodeId": "1", "data": {}},
    {"kind": "edge", "snapshot": "s", "source": "1", "data": {}},
    {"kind": "hyperedge", "snapshot": "s", "members": ["1", "1"], "data": {}},
    {"kind": "event", "snapshot": "s", "data": {}},
    {"kind": "edge", "snapshot": "s", "source": "1", "target": "2",
     "data": {"weight": float("inf")}},
])
def test_records_reject_invalid_shapes(row):
    with pytest.raises(ValidationError):
        EnterpriseRecord.model_validate(row)


@pytest.mark.parametrize("failure", ["dict", "mutated", "missing_feature", "count"])
def test_export_failure_does_not_publish_partial_artifact(tmp_path, validated, failure):
    record = company()
    rows = [record]
    if failure == "dict":
        rows = [record.model_dump()]
    elif failure == "mutated":
        record.data["label"] = 7
    elif failure == "missing_feature":
        record.data["attributes"] = {}
    else:
        rows = []
    output = tmp_path / "enterprises.jsonl"
    output.write_bytes(b"previous artifact")
    with pytest.raises((ValueError, TypeError)):
        export(ExportAdapter(rows), tmp_path, output, validated)
    assert output.read_bytes() == b"previous artifact"
    assert list(tmp_path.iterdir()) == [output]


def test_exported_records_are_accepted_by_business_importer(tmp_path, validated):
    # Read the independent backend decoder to detect producer/consumer contract drift.
    source = Path(__file__).resolve().parents[3] / (
        "backend/src/risk_api/modules/modeling/enterprise_data.py"
    )
    spec = importlib.util.spec_from_file_location("enterprise_import_contract", source)
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    rows = [company(), EnterpriseRecord(kind="person", snapshot="test", nodeId="p1",
                                      data={"attributes": {}}),
            EnterpriseRecord(kind="edge", snapshot="test", source="p1", target="0001", data={}),
            EnterpriseRecord(kind="hyperedge", snapshot="test", members=["0001"], data={}),
            EnterpriseRecord(kind="event", snapshot="test", source="0001", data={})]
    output = tmp_path / "enterprises.jsonl"
    result = export(ExportAdapter(rows), tmp_path, output, validated)
    assert result.counts == {"company": 1, "person": 1, "edge": 1, "hyperedge": 1, "event": 1}
    parsed = list(consumer.records(output))
    assert parsed[0][1]["sourceSha256"] == validated["sha256"]
    assert [row.kind for _, row in parsed[1:]] == [row.kind for row in rows]
    assert parsed[1][1].nodeId == "0001"
    assert json.loads(output.read_text().splitlines()[0])["target"] == "status"


def test_runtime_result_schema_matches_typed_output():
    descriptor = Path(__file__).resolve().parents[2] / "riskgnn/runtime.json"
    schema = json.loads(descriptor.read_text())["operations"]["inspect"]["result_schema"]
    assert schema == InspectionOutput.model_json_schema()
