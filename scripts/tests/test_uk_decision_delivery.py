"""Exercise the public artifact format with tiny files, never synthetic training data."""

import io
import json
import shutil
import sys
import tarfile
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pydantic import ValidationError

from model_service.modules.decision.artifacts.archive import extract, install, package, write_json
from model_service.modules.decision.artifacts.delivery import install_delivery, package_delivery
from model_service.modules.decision.artifacts.manifest import (
    DownloadAsset,
    Release,
    describe,
    digest,
    verify_bundle,
)
from model_service.modules.decision.contracts.input import DEFINITION, input_state, load_contract
from model_service.modules.decision.delivery_cli import main as delivery_main


@pytest.fixture
def delivery(tmp_path):
    definition = tmp_path / "definition"
    shutil.copytree(DEFINITION, definition)
    adapter = tmp_path / "source-adapter"
    adapter.mkdir()
    model = json.loads((definition / "model.json").read_text())
    for name in model["adapter_files"]:
        path = adapter / name
        path.write_bytes(f"test-only artifact: {name}".encode())
        model["adapter_files"][name] = describe(path).model_dump()
    calibration = adapter / "calibration.json"
    write_json(calibration, {"temperature": 0.8826538438450512})
    model["calibration_file"] = describe(calibration).model_dump()
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.json").write_text("test-only base")
    model["base"]["files"] = {"config.json": describe(base / "config.json").model_dump()}
    write_json(definition / "model.json", model)
    archive = tmp_path / "build" / "uk-financial-0.6b-v1.tar.gz"
    release = package(adapter, definition, archive)
    return archive, release, base, adapter, definition


def test_packaging_is_deterministic_and_installation_is_idempotent(delivery, tmp_path):
    archive, release, base, adapter, definition = delivery
    repeated = tmp_path / "repeat" / archive.name
    assert package(adapter, definition, repeated) == release
    assert repeated.read_bytes() == archive.read_bytes()
    destination = tmp_path / "installed"
    install(archive, destination, release, base_from=base)
    install(archive, destination, release, base_from=base)
    manifest, contract = verify_bundle(destination, release, base=destination / "base")
    assert contract.model_version == release.model_version
    assert manifest.model.calibration_status == "available"
    assert (destination / "calibration.json").read_bytes() == (
        adapter / "calibration.json"
    ).read_bytes()
    assert "calibration.json" not in manifest.model.adapter_files
    assert manifest.files["calibration.json"] == manifest.model.calibration_file
    assert {p.name for p in (destination / "adapter").iterdir()} == set(
        manifest.model.adapter_files
    )


def test_calibration_can_be_supplied_separately_and_must_match_the_definition(delivery, tmp_path):
    archive, _, _, adapter, definition = delivery
    calibration = tmp_path / "calibration.json"
    (adapter / "calibration.json").rename(calibration)
    target = tmp_path / "separate" / archive.name
    release = package(adapter, definition, target, calibration=calibration)
    destination = tmp_path / "separate-install"
    install(target, destination, release)
    assert (destination / "calibration.json").read_bytes() == calibration.read_bytes()
    write_json(calibration, {"temperature": 1.2})
    with pytest.raises(ValueError, match="checksum"):
        package(adapter, definition, tmp_path / "modified" / archive.name, calibration=calibration)


def test_missing_corrupt_and_invalid_calibration_are_rejected(delivery, tmp_path):
    archive, release, _, adapter, definition = delivery
    source = adapter / "calibration.json"
    original = source.read_bytes()
    source.unlink()
    with pytest.raises(ValueError, match="Missing"):
        package(adapter, definition, tmp_path / "missing" / archive.name)
    source.write_bytes(original)
    destination = tmp_path / "corrupt-calibration"
    install(archive, destination, release)
    write_json(destination / "calibration.json", {"temperature": 1.2})
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(destination, release)
    # A matching checksum still must not make an invalid temperature executable.
    write_json(source, {"temperature": -1})
    model = json.loads((definition / "model.json").read_text())
    model["calibration_file"] = describe(source).model_dump()
    write_json(definition / "model.json", model)
    with pytest.raises(ValueError, match="temperature"):
        package(adapter, definition, tmp_path / "invalid" / archive.name)


def test_base_can_be_added_after_a_lora_only_install(delivery, tmp_path):
    archive, release, base, _, _ = delivery
    destination = tmp_path / "adapter-first"
    install(archive, destination, release)
    manifest_hash = digest(destination / "manifest.json")
    install(archive, destination, release, base_from=base)
    verify_bundle(destination, release, base=destination / "base")
    assert digest(destination / "manifest.json") == manifest_hash


def test_corrupt_asset_base_and_installed_artifact_are_rejected(delivery, tmp_path):
    archive, release, base, _, _ = delivery
    corrupt = tmp_path / "bad.tar.gz"
    corrupt.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        install(corrupt, tmp_path / "no-install", release)
    assert not (tmp_path / "no-install").exists()
    (base / "config.json").write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        install(archive, tmp_path / "bad-base", release, base_from=base)
    assert not (tmp_path / "bad-base").exists()
    destination = tmp_path / "installed"
    install(archive, destination, release)
    (destination / "adapter/decision_runtime.json").write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(destination, release)
    with pytest.raises(ValueError):
        install(archive, destination, release)


@pytest.mark.parametrize(
    "member_name,kind",
    [
        ("uk-financial-0.6b-v1/../../escape", "file"),
        ("/absolute", "file"),
        ("other/file", "file"),
        ("uk-financial-0.6b-v1/link", "symlink"),
        ("uk-financial-0.6b-v1/link", "hardlink"),
        ("uk-financial-0.6b-v1/file", "duplicate"),
    ],
)
def test_unsafe_archive_members_never_escape_staging(delivery, tmp_path, member_name, kind):
    _, original, _, _, _ = delivery
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        entry = tarfile.TarInfo(member_name)
        entry.size = 1
        if kind in {"symlink", "hardlink"}:
            entry.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            entry.linkname = "../../escape"
            entry.size = 0
        tar.addfile(entry, io.BytesIO(b"x"))
        if kind == "duplicate":
            tar.addfile(entry, io.BytesIO(b"x"))
    release = original.model_copy(
        update={"size": archive.stat().st_size, "sha256": digest(archive)}
    )
    destination = tmp_path / "staging"
    destination.mkdir()
    with pytest.raises(ValueError):
        extract(archive, destination, release)
    assert not (tmp_path / "escape").exists()


def test_definition_mismatch_and_unmanaged_directory_are_preserved(delivery, tmp_path):
    archive, release, _, adapter, definition = delivery
    destination = tmp_path / "existing-model"
    destination.mkdir()
    sentinel = destination / "my-weights"
    sentinel.write_bytes(b"do not delete")
    with pytest.raises(OSError):
        install(archive, destination, release)
    assert sentinel.read_bytes() == b"do not delete"
    (adapter / "decision_runtime.json").write_bytes(b"different version")
    with pytest.raises(ValueError, match="checksum"):
        package(adapter, definition, tmp_path / "new" / archive.name)


def test_frozen_input_contract_and_manifest_versions(delivery, tmp_path):
    archive, release, _, _, _ = delivery
    contract = load_contract()
    changed = deepcopy(contract.model_dump())
    changed["question"]["criteria"] = dict(reversed(list(changed["question"]["criteria"].items())))
    with pytest.raises(ValidationError, match="Candidate order"):
        type(contract).model_validate(changed)
    assert input_state({"state": {"features": {"cash": 0}}}, contract) == '{"features":{"cash":0}}'
    destination = tmp_path / "installed"
    install(archive, destination, release)
    path = destination / "manifest.json"
    value = json.loads(path.read_text())
    value["manifest_version"] = 99
    write_json(path, value)
    with pytest.raises(ValueError, match="release catalog"):
        verify_bundle(destination, release)
    with pytest.raises(ValidationError):
        verify_bundle(destination)


def test_release_catalog_rejects_unsafe_asset_names(delivery):
    _, release, _, _, _ = delivery
    value = release.model_dump()
    value["asset"] = "../model.tar.gz"
    with pytest.raises(ValidationError):
        Release.model_validate(value)


@pytest.fixture
def delivery_set(delivery, tmp_path):
    archive, _, base, adapter, definition = delivery
    source = tmp_path / "financial.zip"
    contract = {
        "contract_version": 1,
        "dataset": {"id": "uk-financial-observations", "name": "UK financial", "version": "test"},
        "adapter": {"id": "uk-financial-jsonl", "version": "1", "config": {}},
    }
    with ZipFile(source, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr("risk_dataset_contract.json", json.dumps(contract))
        # Transport fixtures are opaque files; they are never accepted as training samples.
        for name in (
            "manifest.json", "sample-index.jsonl", "train.financial.jsonl",
            "valid.financial.jsonl", "test.financial.jsonl",
        ):
            zipped.writestr(name, "test-only delivery file")
    target = tmp_path / "release-assets" / archive.name
    release = package_delivery(adapter, definition, target, dataset=source)
    return target.parent, release, base


def test_complete_delivery_is_repeatable_and_preserves_local_data(delivery_set, tmp_path):
    assets, release, base = delivery_set
    destination, data = tmp_path / "model", tmp_path / "financial"
    for _ in range(2):
        installed_zip = install_delivery(assets, release, destination, data, base_from=base)
    verify_bundle(destination, release, base=destination / "base")
    assert installed_zip.read_bytes() == (assets / release.dataset.asset).read_bytes()
    assert (data / "risk_dataset_contract.json").is_file()
    (data / "manifest.json").write_text("local edit")
    with pytest.raises(ValueError, match="checksum"):
        install_delivery(assets, release, destination, data)
    assert (data / "manifest.json").read_text() == "local edit"


def test_dataset_corruption_is_reported_before_installing_a_model(delivery_set, tmp_path):
    assets, release, _ = delivery_set
    with (assets / release.dataset.asset).open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        install_delivery(assets, release, tmp_path / "model", tmp_path / "data")
    assert not (tmp_path / "model").exists()


def test_install_command_downloads_the_release_and_public_base(
    delivery_set, tmp_path, monkeypatch, capsys
):
    assets, release, base = delivery_set
    catalog = tmp_path / "release.json"
    write_json(catalog, release.model_dump())
    assert "publication_status" not in json.loads(catalog.read_text())
    commands = tmp_path / "bin"
    commands.mkdir()
    gh = commands / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import shutil, sys\n"
        "from pathlib import Path\n"
        f"source = Path({str(assets)!r})\n"
        "args = sys.argv[1:]\n"
        "target = Path(args[args.index('--dir') + 1])\n"
        "for index, arg in enumerate(args):\n"
        "    if arg == '--pattern':\n"
        "        shutil.copyfile(source / args[index + 1], target / args[index + 1])\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands))

    def public_base(**kwargs):
        assert kwargs["endpoint"] == "https://huggingface.co"
        assert kwargs["repo_id"] == "Qwen/Qwen3-0.6B"
        assert kwargs["revision"] == "c1899de289a04d12100db370d81485cdf75e47ca"
        shutil.copytree(base, kwargs["local_dir"])

    monkeypatch.setattr(
        "model_service.modules.decision.delivery_cli.snapshot_download", public_base
    )
    monkeypatch.chdir(tmp_path)
    args = [
        "install", "--release", "release.json", "--with-base",
        "--destination", "installed-model", "--dataset-destination", "datasets/financial",
    ]
    assert delivery_main(args) == 0
    verify_bundle(Path("installed-model"), release, base=Path("installed-model/base"))
    assert Path("datasets/financial/risk_dataset_contract.json").is_file()
    assert Path("datasets/financial.zip").is_file()
    assert "Upload this ZIP" in capsys.readouterr().out
    # Subsequent installs reuse the already verified base, including in offline environments.
    assert delivery_main(args[:4] + ["--assets-dir", str(assets)] + args[4:]) == 0


def test_missing_release_is_reported_without_installing(delivery_set, tmp_path, monkeypatch):
    _, release, _ = delivery_set
    catalog = tmp_path / "release.json"
    write_json(catalog, release.model_dump())
    commands = tmp_path / "bin"
    commands.mkdir()
    gh = commands / "gh"
    gh.write_text(f"#!{sys.executable}\nraise SystemExit(1)\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands))
    assert delivery_main([
        "install", "--release", str(catalog), "--destination", str(tmp_path / "model"),
        "--dataset-destination", str(tmp_path / "data"),
    ]) == 1
    assert not (tmp_path / "model").exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "folder\\escape"])
def test_dataset_extraction_never_escapes_its_install_directory(delivery_set, tmp_path, name):
    assets, release, _ = delivery_set
    dataset = assets / release.dataset.asset
    with ZipFile(dataset, "w") as zipped:
        zipped.writestr(name, "never write outside staging")
    release.dataset = DownloadAsset(asset=dataset.name, **describe(dataset).model_dump())
    with pytest.raises(ValueError, match="path"):
        install_delivery(assets, release, tmp_path / "model", tmp_path / "data")
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "model").exists()
