"""Build reproducible Release assets and install verified archives without overwriting models."""

import gzip
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from model_service.modules.decision.artifacts.manifest import (
    Manifest,
    ModelDefinition,
    Release,
    describe,
    digest,
    safe_path,
    verify_bundle,
    verify_files,
)
from model_service.modules.decision.contracts.input import ROOT, InputContract

MAX_FILES = 128
MAX_FILE_BYTES = 128 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def package(
    adapter: Path, definition: Path, output: Path, *, calibration: Path | None = None
) -> Release:
    model = ModelDefinition.model_validate_json((definition / "model.json").read_bytes())
    if output.name != f"{model.model_version}.tar.gz":
        raise ValueError("Output must use the versioned asset filename")
    if output.exists() or output.with_suffix(".release.json").exists():
        raise ValueError("Output already exists; choose a new output directory")
    verify_files(adapter, model.adapter_files)
    contract = InputContract.model_validate_json((definition / "input-contract.json").read_bytes())
    if contract.model_version != model.model_version:
        raise ValueError("Input contract and model definition must have the same version")
    # Keep the original adapter intact; the calibrated model owns a separate root artifact.
    calibration_source = None
    allowed = set(model.adapter_files)
    if model.calibration_status == "available":
        calibration_source = calibration or adapter / "calibration.json"
        assert model.calibration_file is not None
        verify_files(calibration_source.parent, {calibration_source.name: model.calibration_file})
        if calibration_source == adapter / "calibration.json":
            allowed.add("calibration.json")
    elif calibration is not None:
        raise ValueError("This model definition does not allow calibration")
    actual = {p.relative_to(adapter).as_posix() for p in adapter.rglob("*") if p.is_file()}
    if actual != allowed:
        raise ValueError("Adapter directory must contain exactly the versioned file set")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="uk-model-package-") as temporary:
        root = Path(temporary) / model.model_version
        root.mkdir()
        for name in model.adapter_files:
            target = root / "adapter" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(adapter / name, target)
        shutil.copyfile(definition / "input-contract.json", root / "input-contract.json")
        shutil.copytree(definition / "acceptance", root / "acceptance")
        shutil.copyfile(ROOT.joinpath(*safe_path(model.model_card).parts), root / "README.md")
        if calibration_source is not None:
            shutil.copyfile(calibration_source, root / "calibration.json")
        paths = sorted(p for p in root.rglob("*") if p.is_file())
        files = {p.relative_to(root).as_posix(): describe(p) for p in paths}
        manifest = Manifest(
            manifest_version=1,
            runtime_api_version=1,
            model=model,
            compatibility={
                "jevforge_commit": "8986e521b8220dc41ff4de44fb418dc0da02afea",
                "service_lock_sha256": digest(ROOT / "models/service/uv.lock"),
                "loader_sha256": digest(
                    ROOT / "models/uk_decision/src/uk_decision_runtime/runtime.py"
                ),
                "predictor_sha256": digest(
                    ROOT / "models/service/src/model_service/modules/decision/predictor.py"
                ),
                "input_validator_sha256": digest(
                    ROOT / "models/service/src/model_service/modules/decision/contracts/input.py"
                ),
                "calibration_sha256": digest(
                    ROOT / "models/service/src/model_service/modules/decision/calibration.py"
                ),
            },
            files=files,
        )
        write_json(root / "manifest.json", manifest.model_dump())
        verify_bundle(root)
        with output.open("xb") as stream:
            # Fixed headers make repeat builds byte-identical; no timestamps or local names leak.
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
                with tarfile.open(mode="w", fileobj=compressed, format=tarfile.USTAR_FORMAT) as tar:
                    for path in sorted(p for p in root.rglob("*") if p.is_file()):
                        record = tarfile.TarInfo(f"{model.model_version}/{path.relative_to(root)}")
                        record.size = path.stat().st_size
                        record.mode = 0o644
                        with path.open("rb") as contents:
                            tar.addfile(record, contents)
        release = Release(
            model_version=model.model_version,
            tag=f"model-{model.model_version}",
            asset=output.name,
            size=output.stat().st_size,
            sha256=digest(output),
            manifest_sha256=digest(root / "manifest.json"),
            publication_status="prepared",
        )
        write_json(output.with_suffix(".release.json"), release.model_dump())
    return release


def extract(archive: Path, destination: Path, release: Release) -> None:
    if archive.stat().st_size != release.size or digest(archive) != release.sha256:
        raise ValueError("Release archive size or SHA-256 mismatch")
    total = 0
    names: set[str] = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            path = safe_path(member.name)
            if (
                not member.isfile()
                or len(path.parts) < 2
                or path.parts[0] != release.model_version
                or member.name in names
            ):
                raise ValueError(f"Unsupported or duplicate archive member: {member.name}")
            names.add(member.name)
            total += member.size
            if (
                len(names) > MAX_FILES
                or not 0 <= member.size <= MAX_FILE_BYTES
                or total > MAX_TOTAL_BYTES
            ):
                raise ValueError("Release archive exceeds extraction limits")
            target = destination.joinpath(*path.parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            contents = tar.extractfile(member)
            if contents is None:
                raise ValueError("Archive member has no contents")
            with contents, target.open("xb") as output:
                shutil.copyfileobj(contents, output, length=1024 * 1024)
    manifest, _ = verify_bundle(destination, release)
    expected = {f"{release.model_version}/{name}" for name in manifest.files}
    expected.add(f"{release.model_version}/manifest.json")
    if names != expected:
        raise ValueError("Archive members must match the manifest exactly")


def install(
    archive: Path, destination: Path, release: Release, *, base_from: Path | None = None
) -> None:
    if destination.exists():
        # Never replace the developer's previous model or scratch directory.
        verify_bundle(destination, release, base=base_from)
        if (destination / "base").is_dir():
            verify_bundle(destination, release, base=destination / "base")
            return
        if base_from is None:
            return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".uk-model-install-", dir=destination.parent
    ) as temporary:
        stage = Path(temporary) / "model"
        stage.mkdir()
        if destination.exists():
            # Adding a base to a verified LoRA-only install leaves its existing artifacts intact.
            shutil.copytree(destination, stage, dirs_exist_ok=True)
        else:
            extract(archive, stage, release)
        if base_from is not None:
            manifest, _ = verify_bundle(stage, release, base=base_from)
            for name in manifest.model.base.files:
                target = stage / "base" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(base_from / name, target)
            verify_bundle(stage, release, base=stage / "base")
        if destination.exists():
            (stage / "base").rename(destination / "base")
        else:
            stage.rename(destination)
