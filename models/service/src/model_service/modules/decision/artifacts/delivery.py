"""Prepare and install the model and financial dataset from one GitHub Release."""

import json
import shutil
import stat
import tempfile
from pathlib import Path
from zipfile import ZipFile

from model_service.modules.decision.artifacts.archive import install, package, write_json
from model_service.modules.decision.artifacts.manifest import (
    DownloadAsset,
    FileRecord,
    Release,
    describe,
    safe_path,
    verify_files,
)
from model_service.shared.dataset_contract import read_dataset_contract
from model_service.shared.paths import model_root


def unpack_dataset(source: Path, destination: Path) -> dict[str, FileRecord]:
    """Extract a trusted Release ZIP with the same resource bounds as workbench uploads."""
    if not 0 < source.stat().st_size <= 512 * 1024**2:
        raise ValueError("Dataset ZIP must be between 1 byte and 512 MiB")
    files: dict[str, FileRecord] = {}
    with ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > 128 or sum(item.file_size for item in entries) > 2 * 1024**3:
            raise ValueError("Dataset ZIP exceeds extraction limits")
        names: set[str] = set()
        for entry in entries:
            name = entry.filename.rstrip("/") if entry.is_dir() else entry.filename
            path = safe_path(name)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if (
                name in names or entry.flag_bits & 1
                or mode not in {0, stat.S_IFREG, stat.S_IFDIR}
                or entry.file_size > 1024**3
                or entry.file_size > max(1, entry.compress_size) * 200
            ):
                raise ValueError("Unsupported, duplicate or oversized dataset ZIP member")
            names.add(name)
            if entry.is_dir():
                continue
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            files[name] = describe(target)
    return files


def verify_asset(path: Path, asset: DownloadAsset) -> None:
    actual = describe(path)
    if actual.size != asset.size or actual.sha256 != asset.sha256:
        raise ValueError(f"Release asset size or SHA-256 mismatch: {asset.asset}")


def package_delivery(
    adapter: Path,
    definition: Path,
    output: Path,
    *,
    dataset: Path,
    calibration: Path | None = None,
) -> Release:
    contract = read_dataset_contract(dataset)
    identity = contract["adapter"]
    if (identity["id"], identity["version"]) != ("uk-financial-jsonl", "1"):
        raise ValueError("Delivery requires a uk-financial-jsonl / 1 dataset")
    # Reuse the model-owned declaration without importing its research dependencies.
    declaration = model_root() / "riskgnn/dataset_adapters/uk_financial/delivery.json"
    required = json.loads(declaration.read_bytes())["required_files"]
    with ZipFile(dataset) as archive:
        contract_path = next(
            name for name in archive.namelist() if name.endswith("risk_dataset_contract.json")
        )
        root = contract_path.removesuffix("risk_dataset_contract.json")
        if not {root + name for name in required} <= set(archive.namelist()):
            raise ValueError("Financial dataset is missing required delivery files")
    dataset_name = f"uk-financial-{contract['dataset']['version']}.zip"
    dataset_asset = DownloadAsset(asset=dataset_name, **describe(dataset).model_dump())
    names = [output.name, output.with_suffix(".release.json").name, dataset_name]
    if len(names) != len(set(names)) or any((output.parent / name).exists() for name in names):
        raise ValueError("Delivery output already exists; choose a new output directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Prepare a complete local asset set before exposing it to the publisher; never upload here.
    with tempfile.TemporaryDirectory(prefix=".uk-delivery-", dir=output.parent) as temporary:
        stage = Path(temporary)
        release = package(adapter, definition, stage / output.name, calibration=calibration)
        shutil.copyfile(dataset, stage / dataset_name)
        verify_asset(stage / dataset_name, dataset_asset)
        release.dataset = dataset_asset
        write_json(stage / output.with_suffix(".release.json").name, release.model_dump())
        for name in names:
            (stage / name).rename(output.parent / name)
    return release


def install_delivery(
    assets: Path,
    release: Release,
    destination: Path,
    dataset_destination: Path,
    *,
    base_from: Path | None = None,
) -> Path:
    if release.dataset is None:
        raise ValueError("Release does not declare a financial dataset")
    archive = assets / release.asset
    dataset = assets / release.dataset.asset
    verify_asset(archive, release)
    verify_asset(dataset, release.dataset)
    dataset_zip = dataset_destination.with_name(dataset_destination.name + ".zip")
    if dataset_zip.exists():
        verify_asset(dataset_zip, release.dataset)
    dataset_destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".uk-dataset-install-", dir=dataset_destination.parent
    ) as temporary:
        stage = Path(temporary)
        files = unpack_dataset(dataset, stage / "data")
        if dataset_destination.exists():
            # Repeated installs preserve local edits and refuse to mix two dataset versions.
            verify_files(dataset_destination, files)
            actual = {
                item.relative_to(dataset_destination).as_posix()
                for item in dataset_destination.rglob("*")
                if item.is_file()
            }
            if actual != set(files):
                raise ValueError("Dataset directory contains untracked local files")
        install(archive, destination, release, base_from=base_from)
        if not dataset_destination.exists():
            (stage / "data").rename(dataset_destination)
        if not dataset_zip.exists():
            shutil.copyfile(dataset, stage / "dataset.zip")
            (stage / "dataset.zip").rename(dataset_zip)
    return dataset_zip
