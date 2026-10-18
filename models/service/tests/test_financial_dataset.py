import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from model_service.modules.decision.contracts.input import input_state, load_contract
from model_service.modules.decision.mapping import record_input
from riskgnn.dataset_adapters.enterprise import export
from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import inspect, resolve


def file_record(path):
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture(scope="session")
def financial_subset(request, tmp_path_factory):
    default = Path(__file__).resolve().parents[3] / "datasets/uk_financial"
    source = Path(os.getenv("RISK_FINANCIAL_DATA_DIR", str(default)))
    if not (source / "manifest.json").is_file():
        if request.config.getoption("--require-financial-data"):
            pytest.fail("Required financial source is missing; set RISK_FINANCIAL_DATA_DIR")
        pytest.skip("Set RISK_FINANCIAL_DATA_DIR for real financial-source adapter tests")
    target = tmp_path_factory.mktemp("financial-source")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["files"], manifest["splits"] = {}, {}
    index = []
    with (source / "sample-index.jsonl").open() as stream:
        for line in stream:
            value = json.loads(line)
            if value["line"] <= 3:
                index.append(value)
    (target / "sample-index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in index))
    for split in ("train", "valid", "test"):
        filename = f"{split}.financial.jsonl"
        with (source / filename).open() as stream:
            rows = [json.loads(stream.readline()) for _ in range(3)]
        (target / filename).write_text("".join(json.dumps(row) + "\n" for row in rows))
        positives = sum(next(iter(row["expected"].values())) == "event" for row in rows)
        manifest["splits"][split] = {
            "samples": 3,
            "labels": {"1": positives, "0": 3 - positives},
            "companies": len({row["company_id"] for row in index if row["split"] == split}),
        }
        manifest["files"][filename] = file_record(target / filename)
    manifest["files"]["sample-index.jsonl"] = file_record(target / "sample-index.jsonl")
    manifest["subset"] = {
        "rule": "first three source rows per split, integration only",
        "sourceManifest": file_record(source / "manifest.json"),
    }
    (target / "manifest.json").write_text(json.dumps(manifest))
    return target


def test_real_financial_package_and_enterprise_export(financial_subset, tmp_path):
    archive, validated = tmp_path / "financial.zip", tmp_path / "validated"
    package(financial_subset, archive, "uk-financial", "integration-subset")
    inspection = inspect(archive, validated)
    assert inspection["counts"]["company_attr"] == 9
    assert inspection["supportedRunnerIds"] == []
    adapter, _ = resolve(archive)
    records = list(adapter.enterprise_records(validated))
    assert len(records) == 9
    first = records[0]
    document, warnings = record_input(
        adapter.id, adapter.version, first.data["attributes"], load_contract()
    )
    with (financial_subset / "train.financial.jsonl").open() as stream:
        original = json.loads(stream.readline())
    assert not warnings and input_state(document) == input_state(original)
    assert "expected" not in input_state(document)
    result = export(adapter, validated, tmp_path / "enterprises.jsonl", inspection)
    assert result.counts == {"company": 9}
    assert first.data["sourceRecord"]["line"] == 1


@pytest.mark.parametrize("kind", ["checksum", "index", "feature", "question"])
def test_financial_dataset_rejects_corruption(financial_subset, tmp_path, kind):
    source = tmp_path / "source"
    shutil.copytree(financial_subset, source)
    manifest = json.loads((source / "manifest.json").read_text())
    filename = "sample-index.jsonl" if kind == "index" else "train.financial.jsonl"
    lines = (source / filename).read_text().splitlines()
    row = json.loads(lines[0])
    if kind == "index":
        row["line"] = 999
    elif kind in {"feature", "checksum"}:
        row["state"]["features"]["invented_feature"] = 1
    else:
        row["questions"]["formal_insolvency_12m"]["instructions"] = "changed"
    lines[0] = json.dumps(row)
    (source / filename).write_text("\n".join(lines) + "\n")
    if kind != "checksum":
        manifest["files"][filename] = file_record(source / filename)
    (source / "manifest.json").write_text(json.dumps(manifest))
    archive = tmp_path / "bad.zip"
    package(source, archive, "uk-financial", "invalid")
    with pytest.raises(ValueError):
        inspect(archive, tmp_path / "validated")
