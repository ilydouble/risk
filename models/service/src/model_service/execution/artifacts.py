"""Transport integrity only; each adapter owns the meaning of its artifact files."""

import hashlib
import json
import zipfile
from pathlib import Path

from model_service.execution.contracts import ExecutionError, OperationResult
from model_service.files import digest


def inventory(path: Path) -> dict:
    if path.is_symlink() or not path.exists():
        raise ExecutionError("EXECUTION_ARTIFACT_INVALID", "Missing or linked artifact")
    entries = [path] if path.is_file() else sorted(path.rglob("*"))
    files = {}
    for entry in entries:
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise ExecutionError(
                "EXECUTION_ARTIFACT_INVALID", "Artifact contains a link or special file"
            )
        if entry.is_file():
            name = entry.name if path.is_file() else entry.relative_to(path).as_posix()
            files[name] = {"size": entry.stat().st_size, "sha256": digest(entry)}
    if not files:
        raise ExecutionError("EXECUTION_ARTIFACT_INVALID", "Artifact is empty")
    return files


def fingerprint(path: Path) -> str:
    if path.is_file() and not path.is_symlink():
        return digest(path)
    return hashlib.sha256(json.dumps(inventory(path), sort_keys=True).encode()).hexdigest()


def artifact_paths(output: Path, result: OperationResult) -> dict[str, Path]:
    paths = {}
    for role, artifact in result.artifacts.items():
        path = output / artifact.path
        if path == output or not path.resolve().is_relative_to(output.resolve()):
            raise ExecutionError("EXECUTION_ARTIFACT_INVALID", "Artifact escapes output directory")
        # resolve() alone would hide links pointing back inside the allowed directory.
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != output.parent):
            raise ExecutionError("EXECUTION_ARTIFACT_INVALID", "Artifact path contains a link")
        paths[role] = path
    return paths


def pack(directory: Path, target: Path) -> None:
    files = inventory(directory)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(directory / name, name)
