"""Real adapter exports preserve identities and the model's raw feature mapping."""

import json
import subprocess
import sys

import numpy as np
import pytest

from riskgnn.dataset_adapters.enterprise import FORMAT, export
from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve
from riskgnn.workbench.artifacts import asset_digest, read_json


@pytest.fixture(params=["acra", "smesd", "uk"])
def enterprise_source(request, export_zip, datasets, tmp_path):
    if request.param == "acra":
        return export_zip
    source = datasets / ("comrisk_export_v5/smesd" if request.param == "smesd" else "uk_dataset_v1")
    archive = tmp_path / "source.zip"
    package(
        source,
        archive,
        "smesd" if request.param == "smesd" else "uk-companies",
        "enterprise-test",
        overrides={"target_count": 60},
    )
    return archive


def test_real_enterprise_export_matches_prepared_features(enterprise_source, tmp_path):
    validated = tmp_path / "validated"
    inspection = inspect(enterprise_source, validated)
    adapter, contract = resolve(enterprise_source)
    output = tmp_path / "enterprises.jsonl"
    summary = export(adapter, validated, output, inspection)
    assert summary["format"] == FORMAT
    assert summary["counts"]["company"] == inspection["counts"]["company_attr"]
    metadata = adapter.prepare(validated, tmp_path / "prepared", {"target_count": 60})
    ids = read_json(tmp_path / "prepared/ids.json")
    context = dict(np.load(tmp_path / "prepared/context.npz", allow_pickle=False))
    wanted = set(ids[: metadata.get("companyCount", len(ids))])
    company_data = {}
    counts = {}
    references, nodes = set(), set()
    with output.open() as stream:
        header = json.loads(next(stream))
        assert header["datasetContract"] == contract
        assert header["sourceSha256"] == inspection["sha256"]
        for line in stream:
            row = json.loads(line)
            counts[row["kind"]] = counts.get(row["kind"], 0) + 1
            snapshot = row["snapshot"]
            if row["kind"] in {"company", "person"}:
                key = (snapshot, row["nodeId"])
                assert key not in nodes
                nodes.add(key)
                if adapter.id != "sg-comrisk":
                    assert row["data"]["name"] is None, "Never invent a company/person name"
                if row["kind"] == "company" and row["nodeId"] in wanted:
                    company_data[row["nodeId"]] = row["data"]
            else:
                for name in [row.get("source"), row.get("target"), *row.get("members", [])]:
                    if name:
                        references.add((snapshot, name))
    assert counts == summary["counts"]
    assert references <= nodes
    assert wanted <= company_data.keys()
    preprocessing = metadata["preprocessing"]
    for i, name in enumerate(ids[: len(wanted)]):
        raw = company_data[name]["attributes"]
        for j, feature in enumerate(metadata["features"]):
            value = raw[feature]
            if value is not None and feature in preprocessing.get("log1p", []):
                value = np.log1p(np.float32(value))
            if value is None:
                value = preprocessing["fillValues"][j]
            if "mean" in preprocessing:
                value = (value - preprocessing["mean"][j]) / preprocessing["scale"][j]
            assert np.isclose(context["features"][i, j], value, atol=1e-4), feature


def test_export_training_and_predictions_survive_cli_processes(datasets, tmp_path):
    archive = tmp_path / "source.zip"
    package(
        datasets / "comrisk_export_v5/smesd",
        archive,
        "smesd",
        "cli-test",
        overrides={"target_count": 30},
    )

    def operation(name, role, source, format_name, parameters):
        directory = tmp_path / name
        command = {
            "contract_version": 2,
            "runtime_id": "riskgnn",
            "runtime_version": "3",
            "run_id": "enterprise-cli",
            "attempt_id": "1",
            "request_id": "test",
            "directory": str(directory),
            "device": "cpu",
            "resources": {"threads": 2},
            "request": {
                "operation": name,
                "inputs": {
                    role: {
                        "path": str(source),
                        "sha256": asset_digest(source),
                        "format": format_name,
                    }
                },
                "parameters": parameters,
            },
        }
        request = tmp_path / f"{name}-request.json"
        request.write_text(json.dumps(command))
        process = subprocess.run(
            [sys.executable, "-m", "riskgnn.workbench_cli", "--request", str(request)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert process.returncode == 0, process.stderr
        return directory, read_json(directory / "operation-result.json")

    inspected_dir, inspected = operation("inspect", "dataset", archive, "zip", {})
    assert inspected["artifacts"]["enterprises"]["format"] == FORMAT
    assert (inspected_dir / "output/enterprises.jsonl").is_file()
    trained_dir, trained = operation("train", "dataset", archive, "zip", {"epochs": 1})
    model = trained_dir / "output/model"
    before = asset_digest(model)
    _, evaluated = operation("evaluate", "model", model, "riskgnn-plus-model-v1", {})
    assert evaluated["data"]["report"]["independentReload"] is True
    assert asset_digest(model) == before
    company = trained["data"]["companies"][0]
    _, predicted = operation(
        "predict", "model", model, "riskgnn-plus-model-v1", {"company_ids": [company]}
    )
    assert predicted["data"]["items"][0]["companyId"] == company
    assert 0 <= predicted["data"]["items"][0]["probability"] <= 1
    assert 0 <= predicted["data"]["items"][0]["uncertainty"] <= 1
