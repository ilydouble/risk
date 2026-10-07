"""Inspect ZIPs without importing or executing any uploaded code."""

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from service.files import digest

MAX_UPLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024


def unpack(source: Path, target: Path) -> list[dict[str, Any]]:
    if not 0 < source.stat().st_size <= MAX_UPLOAD:
        raise ValueError("ZIP must be between 1 byte and 512 MiB")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > 128:
            raise ValueError("ZIP contains more than 128 entries")
        names: set[str] = set()
        total = 0
        files = []
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in entry.filename
                or not relative.parts
                or ":" in entry.filename
            ):
                raise ValueError("Unsafe ZIP path")
            name = relative.as_posix()
            if name in names or entry.flag_bits & 1:
                raise ValueError("Duplicate or encrypted ZIP member")
            names.add(name)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("ZIP links are not allowed")
            if entry.is_dir():
                continue
            total += entry.file_size
            if (
                total > MAX_EXPANDED
                or entry.file_size > 1024**3
                or entry.file_size > max(1, entry.compress_size) * 200
            ):
                raise ValueError("ZIP expansion exceeds allowed resources")
            destination = target / name
            if not destination.resolve().is_relative_to(target.resolve()):
                raise ValueError("ZIP path escapes destination")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as src, destination.open("wb") as dst:
                # zipfile verifies CRC at EOF; streaming avoids holding the archive in memory.
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            files.append({"path": name, "size": entry.file_size, "sha256": digest(destination)})
    return files


def data_root(directory: Path) -> Path:
    candidates = list(directory.glob("company_attr.parquet"))
    candidates += list(directory.glob("*/company_attr.parquet"))
    if len(candidates) != 1:
        raise ValueError("Expected one comrisk_export directory")
    return candidates[0].parent
