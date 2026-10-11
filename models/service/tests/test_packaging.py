import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest

from riskgnn.dataset_adapters import delivery, packaging
from riskgnn.dataset_adapters.contract import CONTRACT_NAME, read_contract
from riskgnn.dataset_adapters.delivery import delivery_for, preset_details
from riskgnn.dataset_adapters.packaging import package
from riskgnn.dataset_adapters.registry import _ADAPTERS


def test_delivery_declarations_match_registered_adapters():
    assert {(d.adapter_id, d.adapter_version) for d in delivery.catalog()} == set(_ADAPTERS)
    uk = preset_details("uk-companies")
    assert uk["dataset"]["id"] == "uk-companies"
    assert uk["adapter"] == {"id": "uk-dataset-v1", "version": "1"}
    assert uk["defaultConfig"] == {"target_count": 2000}
    assert uk["config"] == uk["defaultConfig"]
    assert {"valid.json", "test.json"} <= set(uk["requiredFiles"])
    changed = preset_details("uk-companies", {"target_count": 60})
    assert changed["config"] == changed["overrides"] == {"target_count": 60}
    assert changed["defaultConfig"] == uk["defaultConfig"]


@pytest.mark.parametrize(
    "config", [{"target_count": True}, {"target_count": 5}, {"target_count": 20001}, {"unknown": 1}]
)
def test_packager_and_adapter_share_config_rejections(config):
    with pytest.raises(ValueError, match="Invalid"):
        preset_details("smesd", config)
    adapter = _ADAPTERS[("smesd", "1")]
    with pytest.raises(ValueError, match="Invalid"):
        adapter.inspect(Path("unused.zip"), Path("unused"), config)


def test_lightweight_cli_never_imports_model_dependencies():
    code = """
import importlib.abc
import runpy
import sys
class LightweightOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'numpy', 'pandas', 'duckdb', 'pyarrow',
                                    'fastapi', 'sqlalchemy', 'model_service'}:
            raise ImportError('Packaging must remain lightweight: ' + fullname)
sys.meta_path.insert(0, LightweightOnly())
sys.argv = ['package_dataset', '--show-preset', 'uk-companies', '--json']
runpy.run_module('riskgnn.dataset_adapters.package_dataset', run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["preset"] == "uk-companies"


def test_missing_files_root_and_unchanged_source_contract(datasets, tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    source = datasets / "comrisk_export_v5/smesd"
    shutil.copy2(source / "train.json", root / "train.json")
    with pytest.raises(ValueError, match="valid.json, test.json"):
        package(root, tmp_path / "missing.zip", "smesd", "v5")
    assert not (tmp_path / "missing.zip").exists()
    for name in ("valid.json", "test.json"):
        shutil.copy2(source / name, root / name)
    old = b'{"source": "old contract is not the binding authority"}'
    (root / CONTRACT_NAME).write_bytes(old)
    result = package(
        root, tmp_path / "ready.zip", "smesd", "new-version", overrides={"target_count": 60}
    )
    assert result["sourceContractIgnored"] is True
    assert result["validation"] == "packaging-only"
    assert result["validationReport"] is None
    assert (root / CONTRACT_NAME).read_bytes() == old
    contract, relative = read_contract(tmp_path / "ready.zip")
    assert relative == "." and contract["dataset"]["version"] == "new-version"
    assert contract["adapter"]["config"] == {"target_count": 60}
    with ZipFile(tmp_path / "ready.zip") as archive:
        assert archive.namelist().count(CONTRACT_NAME) == 1
        assert archive.read("train.json") == (source / "train.json").read_bytes()
    with pytest.raises(ValueError, match="directory"):
        package(tmp_path / "ready.zip", tmp_path / "again.zip", "smesd", "v6")
    with pytest.raises(ValueError, match="outside"):
        package(root, root / "inside.zip", "smesd", "v6")


def test_preset_can_bind_another_dataset_and_adapter_version(datasets, tmp_path, monkeypatch):
    definition = replace(
        delivery_for("smesd", "1"),
        adapter_version="2",
        presets={
            "another-cohort": {"dataset": {"id": "cohort-b"}, "description": "Test binding"},
        },
    )
    monkeypatch.setattr(delivery, "catalog", lambda: (definition,))
    result = package(
        datasets / "comrisk_export_v5/smesd", tmp_path / "v2.zip", "another-cohort", "2026-10-20"
    )
    assert result["contract"]["adapter"]["version"] == "2"
    assert result["contract"]["dataset"]["id"] == "cohort-b"


def test_full_validation_is_explicit_and_failure_does_not_publish(datasets, tmp_path):
    root = datasets / "comrisk_export_v5/smesd"
    result = package(
        root,
        tmp_path / "verified.zip",
        "smesd",
        "v5",
        validate=True,
        validation_python=Path(sys.executable),
    )
    assert result["validation"] == "full"
    assert result["validationReport"]["counts"]["company_attr"] == 3976
    invalid = tmp_path / "invalid"
    shutil.copytree(root, invalid)
    (invalid / "train.json").write_text("broken JSON")
    package(invalid, tmp_path / "unchecked.zip", "smesd", "broken")
    with pytest.raises(ValueError, match="Full validation failed"):
        package(invalid, tmp_path / "failed.zip", "smesd", "broken", validate=True)
    assert not (tmp_path / "failed.zip").exists()
    assert not list(tmp_path.glob(".risk-package-*"))


def test_publication_never_removes_a_competing_output(datasets, tmp_path, monkeypatch):
    output = tmp_path / "existing.zip"

    def competing_writer(*_args):
        output.write_bytes(b"existing delivery")
        return {}

    monkeypatch.setattr(packaging, "full_validation", competing_writer)
    with pytest.raises(FileExistsError):
        package(datasets / "comrisk_export_v5/smesd", output, "smesd", "v5", validate=True)
    assert output.read_bytes() == b"existing delivery"
    assert not list(tmp_path.glob(".risk-package-*"))
