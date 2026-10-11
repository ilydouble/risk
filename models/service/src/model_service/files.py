"""Portable, content-addressed artifact files. Manifests never contain absolute paths."""

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    temporary.replace(path)


def seal(directory: Path, *, kind: str, metadata: dict[str, Any]) -> dict[str, Any]:
    files = {
        p.relative_to(directory).as_posix(): {"size": p.stat().st_size, "sha256": digest(p)}
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    manifest = {"formatVersion": 1, "kind": kind, **metadata, "files": files}
    write_json(directory / "manifest.json", manifest)
    return manifest


def verify(directory: Path, kind: str) -> dict[str, Any]:
    manifest = read_json(directory / "manifest.json")
    if manifest.get("formatVersion") != 1 or manifest.get("kind") != kind:
        raise ValueError("Unsupported artifact format")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Artifact file list is empty")
    required = {"context.npz", "ids.json", "metadata.json"}
    if kind == "riskgnn-model-v1":
        required.add("weights.pt")
    if not required.issubset(files):
        raise ValueError("Artifact is missing required files")
    for name, expected in files.items():
        relative = PurePosixPath(name)
        path = directory / name
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Invalid manifest path")
        if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
            raise ValueError("Artifact path escapes its directory")
        if not path.is_file() or path.stat().st_size != expected["size"]:
            raise ValueError(f"Artifact file missing or wrong size: {name}")
        if digest(path) != expected["sha256"]:
            raise ValueError(f"Artifact checksum mismatch: {name}")
    return manifest


def export_zip(directory: Path, target: Path) -> None:
    verify(directory, "riskgnn-model-v1")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = read_json(directory / "manifest.json")
        for name in [*manifest["files"], "manifest.json"]:
            archive.write(directory / name, name)
