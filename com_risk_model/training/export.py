"""Export a selected run as a portable, validated Release attachment."""

import shutil
import tarfile
import tempfile
from pathlib import Path

import torch
from com_risk_runtime.artifacts import ARTIFACT_FILES, build_manifest, validate_bundle
from com_risk_runtime.predictor import Predictor


def export_bundle(run: Path, version: str, snapshot: Path, output: Path) -> Path:
    # Validate the version before using it as a directory or archive member name.
    manifest = build_manifest(run, version, snapshot)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / version
    archive = output / f"{version}.tar.gz"
    if destination.exists() or archive.exists():
        raise FileExistsError(f"export already exists: {version}; choose a new version")
    with tempfile.TemporaryDirectory(prefix=".export-", dir=output) as temporary:
        package = Path(temporary) / version
        package.mkdir()
        for name in ARTIFACT_FILES:
            shutil.copyfile(run / name, package / name)
        (package / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
        bundle = validate_bundle(package, snapshot, expected_version=version)
        torch.set_num_threads(1)
        first = next(n.id for n in bundle.dataset.nodes if n.kind == "company")
        Predictor(package).predict(bundle.dataset, [first])
        temporary_archive = Path(temporary) / archive.name
        with tarfile.open(temporary_archive, "w:gz") as stream:
            stream.add(package, arcname=version, recursive=False)
            for name in (*ARTIFACT_FILES, "manifest.json"):
                stream.add(package / name, arcname=f"{version}/{name}")
        package.rename(destination)
        temporary_archive.rename(archive)
    return archive
