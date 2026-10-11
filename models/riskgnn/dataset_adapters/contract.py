"""Dataset identity and adapter selection, never uploaded Python entry points."""

import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from jsonschema import Draft202012Validator

CONTRACT_NAME = "risk_dataset_contract.json"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "risk_dataset_contract.schema.json"


def read_contract(source: Path) -> tuple[dict, str]:
    with ZipFile(source) as archive:
        members = [
            info
            for info in archive.infolist()
            if PurePosixPath(info.filename).name == CONTRACT_NAME
        ]
        if len(members) != 1:
            raise ValueError("Expected exactly one risk_dataset_contract.json")
        info = members[0]
        relative = PurePosixPath(info.filename)
        if (
            len(relative.parts) > 2
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in info.filename
        ):
            raise ValueError("Contract must be at ZIP root or in one top-level directory")
        if info.file_size > 65536 or info.flag_bits & 1:
            raise ValueError("Dataset contract is too large or encrypted")
        contract = json.loads(archive.read(info))
    Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(contract)
    return contract, relative.parent.as_posix()
