import json
from zipfile import ZipFile

import pytest
from jsonschema.exceptions import ValidationError as SchemaValidationError

from model_service.execution.contracts import ExecutionError
from model_service.shared.dataset_contract import read_dataset_contract
from riskgnn.dataset_adapters.contract import read_contract
from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import resolve

CONTRACT = {
    "contract_version": 1,
    "dataset": {"id": "example", "version": "1"},
    "adapter": {"id": "sg-comrisk", "version": "1", "config": {}},
}


def write_zip(path, entries):
    with ZipFile(path, "w") as archive:
        for name, value in entries:
            archive.writestr(name, json.dumps(value))


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [("risk_dataset_contract.json", {**CONTRACT, "contract_version": 99})],
        [("risk_dataset_contract.json", {**CONTRACT, "entrypoint": "uploaded.py"})],
        [("../risk_dataset_contract.json", CONTRACT)],
        [("a/b/risk_dataset_contract.json", CONTRACT)],
        [("risk_dataset_contract.json", CONTRACT), ("a/risk_dataset_contract.json", CONTRACT)],
    ],
)
def test_required_unambiguous_versioned_contract(tmp_path, entries):
    source = tmp_path / "input.zip"
    write_zip(source, entries)
    with pytest.raises(ExecutionError):
        read_dataset_contract(source)
    with pytest.raises((ValueError, SchemaValidationError)):
        read_contract(source)


def test_contract_selects_data_adapter_not_uploaded_code(export_zip, tmp_path):
    contract = read_dataset_contract(export_zip)
    adapter, model_contract = resolve(export_zip)
    assert contract == model_contract
    assert adapter.id == "sg-comrisk" and adapter.trainable
    changed = {**CONTRACT, "adapter": {"id": "uploaded-python", "version": "1", "config": {}}}
    source = tmp_path / "unknown.zip"
    write_zip(source, [("risk_dataset_contract.json", changed)])
    assert read_dataset_contract(source) == changed
    with pytest.raises(ValueError, match="not supported"):
        resolve(source)
    assert (tmp_path / "source/load_comrisk.py").is_file()


def test_packaging_creates_new_zip_and_preserves_bytes(tmp_path, acra_source):
    source = acra_source / "company_attr.parquet"
    before = source.read_bytes()
    output = tmp_path / "dataset.zip"
    package(acra_source, output, "acra-companies", "1")
    assert source.read_bytes() == before
    assert read_dataset_contract(output)["dataset"]["id"] == "acra"
    assert read_dataset_contract(output)["dataset"]["version"] == "1"
    with ZipFile(output) as archive:
        assert archive.read("company_attr.parquet") == before
    with pytest.raises(ValueError):
        package(acra_source, output, "acra-companies", "1")
