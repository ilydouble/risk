"""Lightweight directory packager; repository presets own the adapter binding."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from riskgnn.dataset_adapters.archive import MAX_EXPANDED, MAX_FILE, MAX_MEMBERS, check_archive
from riskgnn.dataset_adapters.contract import CONTRACT_NAME, validate_contract
from riskgnn.dataset_adapters.delivery import delivery_for, preset_details, relative_file


def source_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Dataset links are not allowed: {path}")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Dataset contains a non-regular file: {path}")
        relative_file(relative)
        if path.name == CONTRACT_NAME:
            if relative != CONTRACT_NAME:
                raise ValueError("Nested dataset contracts are not allowed; select one data root")
            continue  # The preset is authoritative; never modify the source contract.
        size = path.stat().st_size
        total += size
        if size > MAX_FILE or total > MAX_EXPANDED or len(paths) + 2 > MAX_MEMBERS:
            raise ValueError("Dataset exceeds file/count/expanded-size limits")
        paths.append(path)
    return paths


def full_validation(archive: Path, python: Path | None) -> dict:
    # Model imports live in a separate CLI, keeping the default packager dependency-light.
    # Preserve a venv's interpreter path: resolving its symlink would lose the environment.
    executable = str(python.absolute()) if python is not None else sys.executable
    with tempfile.TemporaryDirectory(prefix="risk-package-validation-") as work:
        report = Path(work) / "report.json"
        result = subprocess.run(
            [
                executable,
                "-m",
                "riskgnn.dataset_adapters.validate_package",
                "--input",
                str(archive),
                "--report",
                str(report),
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()[-3000:]
            raise ValueError(
                "Full validation failed. Use --validation-python with a model environment.\n"
                + detail
            )
        return json.loads(report.read_text())


def package(
    data_dir: Path,
    output: Path,
    preset: str,
    dataset_version: str,
    *,
    overrides: dict | None = None,
    validate: bool = False,
    validation_python: Path | None = None,
) -> dict:
    details = preset_details(preset, overrides)
    root = data_dir.resolve()
    if not root.is_dir():
        raise ValueError("--data-dir must be an existing directory; extract ZIP inputs first")
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; choose a new ZIP path")
    if output.resolve().is_relative_to(root):
        raise ValueError("Output must be outside the data directory")
    if validation_python is not None and not validate:
        raise ValueError("--validation-python requires --validate")
    definition = delivery_for(details["adapter"]["id"], details["adapter"]["version"])
    definition.check_files(root)
    files = source_files(root)
    contract = {
        "contract_version": 1,
        "dataset": {**details["dataset"], "version": dataset_version},
        "adapter": {**details["adapter"], "config": details["config"]},
    }
    validate_contract(contract)
    contract_bytes = json.dumps(
        contract, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix=".risk-package-", suffix=".zip", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for path in files:
                before = path.stat()
                with (
                    path.open("rb") as source,
                    archive.open(path.relative_to(root).as_posix(), "w") as target,
                ):
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f"Source changed while packaging: {path}")
            archive.writestr(CONTRACT_NAME, contract_bytes)
        check_archive(temporary)
        report = full_validation(temporary, validation_python) if validate else None
        # Publish atomically without replacing a file that appeared during a long pack/validation.
        os.link(temporary, output)
        return {
            "preset": preset,
            "dataDir": str(root),
            "contract": contract,
            "defaultConfig": details["defaultConfig"],
            "overrides": details["overrides"],
            "fileCount": len(files) + 1,
            "output": str(output),
            "sizeBytes": output.stat().st_size,
            "sourceContractIgnored": (root / CONTRACT_NAME).exists(),
            "validation": "full" if validate else "packaging-only",
            "validationReport": report,
        }
    finally:
        temporary.unlink(missing_ok=True)
