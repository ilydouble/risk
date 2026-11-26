"""Read the workbench identity from a supported Data Package ZIP."""

import json
from pathlib import Path
from zipfile import ZipFile

from riskgnn.dataset_adapters.contract import CONTRACT_NAME, validate_contract
from riskgnn.dataset_adapters.delivery import relative_file

PROFILE = "https://datapackage.org/profiles/2.0/datapackage.json"
PACKAGE_FILE = "datapackage.json"
TASK_FILE = "task.json"
PACKAGES = {
    "uk-h12-migration-acceptance": ("uk-companies", "uk-dataset-v1", "2"),
    "smesd-v5-migration-acceptance": ("smesd", "smesd", "1"),
    "acra": ("acra", "sg-comrisk", "1"),
    "hat": ("hat", "research-parquet", "1"),
    "figraph": ("figraph", "research-parquet", "1"),
    "msgraphfin": ("msgraphfin", "research-parquet", "1"),
}


def _json_member(archive: ZipFile, name: str) -> dict:
    members = [item for item in archive.infolist() if item.filename == name]
    if len(members) != 1 or members[0].file_size > 1024 * 1024 or members[0].flag_bits & 1:
        raise ValueError(f"Expected exactly one small, unencrypted {name}")
    result = json.loads(archive.read(members[0]))
    if not isinstance(result, dict):
        raise ValueError(f"Expected an object in {name}")
    return result


def identify(source: Path) -> tuple[dict, dict] | None:
    with ZipFile(source) as archive:
        names = set(archive.namelist())
        if not {PACKAGE_FILE, TASK_FILE}.issubset(names):
            return None
        descriptor, task = (_json_member(archive, name) for name in (PACKAGE_FILE, TASK_FILE))
        name = descriptor.get("name")
        expected = PACKAGES.get(name) if isinstance(name, str) else None
        if descriptor.get("$schema") != PROFILE or expected is None:
            raise ValueError("Unsupported standard data package profile or name")
        dataset_id, adapter_id, adapter_version = expected
        dataset = task.get("dataset", {})
        if not isinstance(dataset, dict) or dataset.get("id") != dataset_id:
            raise ValueError("Standard package task dataset identity does not match its profile")
        if adapter_id in {"smesd", "uk-dataset-v1"}:
            contract = _json_member(archive, CONTRACT_NAME)
        else:
            version = descriptor.get("version")
            if not isinstance(version, str) or not version:
                raise ValueError("Standard data package version is required")
            contract = {
                "contract_version": 1,
                "dataset": {
                    "id": dataset_id,
                    "name": dataset.get("name", dataset_id),
                    "version": f"datapackage-{version}",
                },
                "adapter": {"id": adapter_id, "version": adapter_version, "config": {}},
            }
        validate_contract(contract)
        identity = contract["adapter"]
        if (identity["id"], identity["version"]) != (adapter_id, adapter_version) or contract[
            "dataset"
        ]["id"] != dataset_id:
            raise ValueError("Embedded dataset contract does not match the standard package")
        return contract, descriptor


def check_resources(descriptor: dict, files: list[dict]) -> None:
    uploaded = {file["path"]: file["sha256"] for file in files}
    resources = descriptor.get("resources")
    if not isinstance(resources, list) or not resources:
        raise ValueError("Standard data package requires resource declarations")
    seen = set()
    for entry in resources:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Invalid standard data package resource")
        path = relative_file(entry["path"])
        if len(path.parts) != 1 or path.name in seen or path.name == PACKAGE_FILE:
            raise ValueError("Standard data package resources must be unique ZIP root files")
        if path.name not in uploaded or entry.get("hash") != f"sha256:{uploaded[path.name]}":
            raise ValueError(f"Standard package checksum mismatch: {path}")
        seen.add(path.name)
    if seen != set(uploaded) - {PACKAGE_FILE}:
        raise ValueError("Standard package contains undeclared resources")
