"""Lightweight, repository-owned delivery rules; never import a model to package data."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from riskgnn.dataset_adapters.contract import CONTRACT_NAME

ROOT = Path(__file__).resolve().parent


def relative_file(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or path.as_posix() != name
    ):
        raise ValueError(f"Unsafe dataset file path: {name}")
    return path


@dataclass(frozen=True)
class Delivery:
    path: Path
    adapter_id: str
    adapter_version: str
    required_files: tuple[str, ...]
    config_schema: dict[str, Any]
    default_config: dict[str, Any]
    presets: dict[str, dict[str, Any]]

    def config(self, values: dict) -> dict:
        if not isinstance(values, dict):
            raise ValueError("Adapter config must be an object")
        result = {**self.default_config, **values}
        try:
            Draft202012Validator(self.config_schema).validate(result)
        except ValidationError as error:
            field = ".".join(map(str, error.path)) or "config"
            raise ValueError(f"Invalid {self.adapter_id} {field}: {error.message}") from error
        return result

    def check_files(self, root: Path) -> None:
        missing = [name for name in self.required_files if not (root / name).is_file()]
        if missing:
            raise ValueError("Missing required files in data root: " + ", ".join(missing))
        for name in self.required_files:
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Required file must stay inside data root: {name}")


@lru_cache
def catalog() -> tuple[Delivery, ...]:
    schema = json.loads((ROOT / "delivery.schema.json").read_text())
    definitions = []
    identities: set[tuple[str, str]] = set()
    names: set[str] = set()
    # Discovery is limited to trusted JSON in the repository, never upload directories.
    for path in sorted(ROOT.glob("*/delivery.json")):
        raw = json.loads(path.read_text())
        Draft202012Validator(schema).validate(raw)
        Draft202012Validator.check_schema(raw["config_schema"])
        if raw["config_schema"].get("type") != "object":
            raise ValueError(f"Config schema must describe an object: {path}")
        for name in raw["required_files"]:
            if relative_file(name).name == CONTRACT_NAME:
                raise ValueError("The generated contract is not a required source file")
        definition = Delivery(
            path,
            raw["adapter"]["id"],
            raw["adapter"]["version"],
            tuple(raw["required_files"]),
            raw["config_schema"],
            raw["default_config"],
            raw["presets"],
        )
        identity = (definition.adapter_id, definition.adapter_version)
        if identity in identities or names.intersection(definition.presets):
            raise ValueError(f"Duplicate adapter identity or preset: {path}")
        identities.add(identity)
        names.update(definition.presets)
        definition.config({})
        for preset in definition.presets.values():
            definition.config(preset.get("config", {}))
        definitions.append(definition)
    return tuple(definitions)


def delivery_for(adapter_id: str, version: str) -> Delivery:
    for definition in catalog():
        if (definition.adapter_id, definition.adapter_version) == (adapter_id, version):
            return definition
    raise ValueError(f"No delivery rules for adapter {adapter_id} / {version}")


def preset_details(name: str, overrides: dict | None = None) -> dict:
    for definition in catalog():
        if name not in definition.presets:
            continue
        preset = definition.presets[name]
        defaults = definition.config(preset.get("config", {}))
        return {
            "preset": name,
            "description": preset["description"],
            "definition": str(definition.path),
            "dataset": dict(preset["dataset"]),
            "adapter": {"id": definition.adapter_id, "version": definition.adapter_version},
            "defaultConfig": defaults,
            "overrides": overrides or {},
            "config": definition.config({**defaults, **(overrides or {})}),
            "requiredFiles": list(definition.required_files),
            "configSchema": definition.config_schema,
            "userSupplied": ["data-dir", "dataset-version", "output"],
        }
    raise ValueError(f"Unknown preset: {name}; use --list-presets")
