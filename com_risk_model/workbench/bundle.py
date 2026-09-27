from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from pydantic import ValidationError

from workbench.schema import BundleMetadata


class BundleValidationError(ValueError):
    """The uploaded archive does not satisfy the Bundle v1 contract."""


@dataclass(frozen=True)
class BundleLimits:
    max_compressed_bytes: int = 512 * 1024 * 1024
    max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_file_count: int = 6
    max_member_bytes: int = 1024 * 1024 * 1024
    max_compression_ratio: int = 200
    max_metadata_bytes: int = 1024 * 1024


DEFAULT_LIMITS = BundleLimits()


@dataclass(frozen=True)
class ValidatedBundle:
    metadata: BundleMetadata
    compressed_size: int
    uncompressed_size: int
    members: tuple[str, ...]


def _source_size(source: bytes | bytearray | Path | str) -> int:
    if isinstance(source, (bytes, bytearray)):
        return len(source)
    return Path(source).stat().st_size


def _open_source(source: bytes | bytearray | Path | str) -> BinaryIO:
    if isinstance(source, (bytes, bytearray)):
        return io.BytesIO(source)
    return Path(source).open("rb")


def _validate_member(info: zipfile.ZipInfo, limits: BundleLimits) -> None:
    path = PurePosixPath(info.filename)
    if (
        info.filename.endswith("/")
        or path.is_absolute()
        or len(path.parts) != 1
        or path.name in {"", ".", ".."}
    ):
        raise BundleValidationError("all files must be regular files at the ZIP root")
    if info.flag_bits & 0x1:
        raise BundleValidationError("encrypted ZIP members are not supported")
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if file_type not in {0, stat.S_IFREG}:
        raise BundleValidationError("links and non-regular ZIP members are not supported")
    if info.file_size > limits.max_member_bytes:
        raise BundleValidationError(f"member exceeds size limit: {info.filename}")
    if info.file_size and info.compress_size == 0:
        raise BundleValidationError("invalid compressed member size")
    if info.compress_size and info.file_size / info.compress_size > limits.max_compression_ratio:
        raise BundleValidationError(f"compression ratio is too high: {info.filename}")


def _sha256_member(archive: zipfile.ZipFile, name: str, limit: int) -> str:
    digest = hashlib.sha256()
    total = 0
    with archive.open(name) as stream:
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise BundleValidationError(f"member exceeds declared limit: {name}")
            digest.update(chunk)
    return digest.hexdigest()


def validate_bundle(
    source: bytes | bytearray | Path | str,
    limits: BundleLimits = DEFAULT_LIMITS,
) -> ValidatedBundle:
    compressed_size = _source_size(source)
    if compressed_size <= 0 or compressed_size > limits.max_compressed_bytes:
        raise BundleValidationError("bundle compressed size is outside the allowed range")
    try:
        with _open_source(source) as raw, zipfile.ZipFile(raw) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) > limits.max_file_count or len(names) != len(set(names)):
                raise BundleValidationError("bundle contains too many or duplicate files")
            for info in infos:
                _validate_member(info, limits)
            total_size = sum(info.file_size for info in infos)
            if total_size > limits.max_uncompressed_bytes:
                raise BundleValidationError("bundle uncompressed size exceeds the limit")
            if "metadata.json" not in names:
                raise BundleValidationError("metadata.json is required")
            metadata_info = archive.getinfo("metadata.json")
            if metadata_info.file_size > limits.max_metadata_bytes:
                raise BundleValidationError("metadata.json exceeds the size limit")
            try:
                metadata = BundleMetadata.model_validate_json(archive.read("metadata.json"))
            except (ValidationError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise BundleValidationError("metadata.json is invalid") from error
            declared = {spec.path: spec for spec in metadata.file_specs().values()}
            expected = {"metadata.json", *declared}
            if set(names) != expected:
                missing = expected.difference(names)
                unknown = set(names).difference(expected)
                raise BundleValidationError(
                    f"bundle members do not match metadata; missing={sorted(missing)}, "
                    f"unknown={sorted(unknown)}"
                )
            for name, spec in declared.items():
                info = archive.getinfo(name)
                if info.file_size != spec.size_bytes:
                    raise BundleValidationError(f"size mismatch for {name}")
                if _sha256_member(archive, name, spec.size_bytes) != spec.sha256:
                    raise BundleValidationError(f"SHA-256 mismatch for {name}")
    except (zipfile.BadZipFile, OSError) as error:
        raise BundleValidationError("uploaded file is not a readable ZIP archive") from error
    return ValidatedBundle(metadata, compressed_size, total_size, tuple(names))
