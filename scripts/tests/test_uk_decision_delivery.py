"""Exercise the public artifact format with tiny files, never synthetic training data."""

import io
import json
import shutil
import tarfile
from copy import deepcopy

import pytest
from pydantic import ValidationError

from scripts.uk_decision.archive import extract, install, package, write_json
from scripts.uk_decision.input_contract import DEFINITION, input_state, load_contract
from scripts.uk_decision.manifest import Release, describe, digest, verify_bundle


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
    assert manifest.model.calibration_status == "unavailable"
    assert not (destination / "calibration.json").exists()
    assert {p.name for p in (destination / "adapter").iterdir()} == set(
        manifest.model.adapter_files
    )


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
