"""Strict, versioned model metadata and artifact integrity checks."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator

from model_service.modules.decision.calibration import load_temperature
from model_service.modules.decision.contracts.input import (
    ContractModel,
    InputContract,
    load_contract,
)

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,79}$")]


class FileRecord(ContractModel):
    size: int = Field(ge=0)
    sha256: Sha256


class BaseModelSpec(ContractModel):
    repo_id: str
    revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    tokenizer_source: Literal["base"]
    files: dict[str, FileRecord]


class ModelDefinition(ContractModel):
    model_version: Version
    model_card: str
    base: BaseModelSpec
    adapter_files: dict[str, FileRecord]
    calibration_status: Literal["unavailable", "available"]
    calibration_file: FileRecord | None = None
    server_reference_status: Literal["unavailable", "available"]
    evaluation: dict

    @model_validator(mode="after")
    def validate_calibration(self) -> "ModelDefinition":
        if (self.calibration_status == "available") != (self.calibration_file is not None):
            raise ValueError("Calibration availability requires its versioned file record")
        return self


class Manifest(ContractModel):
    manifest_version: Literal[1]
    runtime_api_version: Literal[1]
    model: ModelDefinition
    compatibility: dict[str, str]
    files: dict[str, FileRecord]


class DownloadAsset(FileRecord):
    asset: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    size: int = Field(gt=0)


class Release(DownloadAsset):
    model_version: Version
    repository: Literal["ilydouble/risk"] = "ilydouble/risk"
    tag: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")
    manifest_sha256: Sha256
    dataset: DownloadAsset | None = None

    @model_validator(mode="after")
    def validate_asset(self) -> "Release":
        if self.asset != f"{self.model_version}.tar.gz":
            raise ValueError("Asset name must match model version")
        names = [self.asset] + ([self.dataset.asset] if self.dataset else [])
        if len(names) != len(set(names)):
            raise ValueError("Release assets must have distinct filenames")
        return self


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or path.as_posix() != name
        or any(part in {".", ".."} for part in name.split("/"))
        or "\\" in name
        or ":" in name
        or any(ord(c) < 32 for c in name)
    ):
        raise ValueError(f"Invalid artifact path: {name!r}")
    return path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def describe(path: Path) -> FileRecord:
    return FileRecord(size=path.stat().st_size, sha256=digest(path))


def verify_files(root: Path, files: dict[str, FileRecord]) -> None:
    for name, expected in files.items():
        path = root.joinpath(*safe_path(name).parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents if parent != root)
        ):
            raise ValueError(f"Missing or unsupported model file: {name}")
        if describe(path) != expected:
            raise ValueError(f"Model file checksum mismatch: {name}")


def verify_bundle(
    root: Path, release: Release | None = None, *, base: Path | None = None
) -> tuple[Manifest, InputContract]:
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Manifest cannot be a symlink")
    if release and digest(manifest_path) != release.manifest_sha256:
        raise ValueError("Manifest does not match the release catalog")
    manifest = Manifest.model_validate_json(manifest_path.read_bytes())
    if release and manifest.model.model_version != release.model_version:
        raise ValueError("Model version does not match the release catalog")
    required = {
        "input-contract.json",
        "README.md",
        "acceptance/input.json",
        "acceptance/reference.json",
    }
    required.update(f"adapter/{name}" for name in manifest.model.adapter_files)
    if not required <= manifest.files.keys() or "manifest.json" in manifest.files:
        raise ValueError("Manifest is missing required artifacts")
    verify_files(root, manifest.files)
    adapter = {f"adapter/{name}": value for name, value in manifest.model.adapter_files.items()}
    if any(manifest.files[name] != value for name, value in adapter.items()):
        raise ValueError("Adapter files must match model metadata")
    contract = load_contract(root / "input-contract.json")
    if contract.model_version != manifest.model.model_version:
        raise ValueError("Input contract must match model version")
    has_calibration = "calibration.json" in manifest.files
    if has_calibration != (manifest.model.calibration_status == "available"):
        raise ValueError("Calibration availability does not match manifest")
    if has_calibration:
        if manifest.files["calibration.json"] != manifest.model.calibration_file:
            raise ValueError("Calibration file must match model metadata")
        load_temperature(root / "calibration.json")
    if base is not None:
        verify_files(base, manifest.model.base.files)
    return manifest, contract
