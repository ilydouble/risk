"""Versioned model bundle contract shared by exporters, local tools and the API."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .schema import Dataset, Record

ARTIFACT_FILES = ("weights.pt", "metadata.json", "metrics.json")


class FileDigest(Record):
    bytes: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ArtifactFile(FileDigest):
    path: str

    @field_validator("path")
    @classmethod
    def package_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or ":" in value
            or path.as_posix() != value
            or value not in ARTIFACT_FILES
        ):
            raise ValueError("manifest path must name a required package-relative file")
        return value


class Snapshot(FileDigest):
    name: str = Field(min_length=1)
    company_count: int = Field(ge=1)


class Manifest(Record):
    manifest_version: Literal[1] = 1
    runtime_api_version: Literal[1] = 1
    model_version: str
    files: list[ArtifactFile]
    snapshot: Snapshot

    @field_validator("model_version")
    @classmethod
    def version_directory(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError("model version must be a single directory name")
        return value

    @model_validator(mode="after")
    def required_files(self) -> "Manifest":
        if len(self.files) != len(ARTIFACT_FILES) or {f.path for f in self.files} != set(
            ARTIFACT_FILES
        ):
            raise ValueError("manifest must contain each required artifact exactly once")
        return self


@dataclass(frozen=True)
class ValidatedBundle:
    manifest: Manifest
    dataset: Dataset
    metadata: dict[str, Any]
    metrics: dict[str, Any]


def file_digest(path: Path) -> FileDigest:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return FileDigest(bytes=path.stat().st_size, sha256=digest)


def build_manifest(model_dir: Path, model_version: str, data_path: Path) -> Manifest:
    dataset = Dataset.read(data_path)
    return Manifest(
        model_version=model_version,
        files=[
            ArtifactFile(path=name, **file_digest(model_dir / name).model_dump())
            for name in ARTIFACT_FILES
        ],
        snapshot=Snapshot(
            name=dataset.name,
            company_count=sum(n.kind == "company" for n in dataset.nodes),
            **file_digest(data_path).model_dump(),
        ),
    )


def validate_bundle(
    model_dir: Path, data_path: Path, *, expected_version: str | None = None
) -> ValidatedBundle:
    manifest = Manifest.model_validate_json((model_dir / "manifest.json").read_text())
    if expected_version is not None and manifest.model_version != expected_version:
        raise ValueError("selected model version differs from manifest")
    for item in manifest.files:
        path = model_dir / item.path
        # A symlink must not redirect validation to an artifact outside the mounted package.
        if not path.resolve().is_relative_to(model_dir.resolve()):
            raise ValueError(f"artifact escapes model directory: {item.path}")
        if file_digest(path) != FileDigest(bytes=item.bytes, sha256=item.sha256):
            raise ValueError(f"artifact checksum/size mismatch: {item.path}")
    snapshot = manifest.snapshot
    if file_digest(data_path) != FileDigest(bytes=snapshot.bytes, sha256=snapshot.sha256):
        raise ValueError("test snapshot checksum/size mismatch")
    dataset = Dataset.read(data_path)
    if dataset.name != snapshot.name or sum(n.kind == "company" for n in dataset.nodes) != (
        snapshot.company_count
    ):
        raise ValueError("test snapshot identity/count mismatch")
    metadata = json.loads((model_dir / "metadata.json").read_text())
    if metadata.get("version") != 2:
        raise ValueError("unsupported metadata version; expected 2")
    # Training records a canonical dataset hash; the manifest additionally checks original bytes.
    canonical = hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()
    if metadata["dataset_sha256"]["test"] != canonical:
        raise ValueError("test snapshot does not match selected training metadata")
    for key in ("feature_names", "relation_names", "hyperedge_types"):
        if metadata["schema"][key] != getattr(dataset, key):
            raise ValueError(f"snapshot schema mismatch: {key}")
    if metadata["target_description"] != dataset.target_description:
        raise ValueError("snapshot target mismatch")
    metrics = json.loads((model_dir / "metrics.json").read_text())
    expected_metadata = {k: v for k, v in metadata.items() if k not in {"prior", "preprocessor"}}
    if metrics["metadata"] != expected_metadata:
        raise ValueError("saved metrics do not match selected model metadata")
    if not isinstance(metrics["model"]["test"], dict) or not isinstance(metrics["notes"], list):
        raise ValueError("invalid saved evaluation report")
    return ValidatedBundle(manifest, dataset, metadata, metrics)
