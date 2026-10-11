"""Outer upload contract only; column/label/split semantics belong to the model."""

import json
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from model_service.execution.contracts import ExecutionError
from model_service.execution.runtime import dataset_schema


def read_dataset_contract(source: Path) -> dict:
    try:
        with ZipFile(source) as archive:
            members = [
                info
                for info in archive.infolist()
                if PurePosixPath(info.filename).name == "risk_dataset_contract.json"
            ]
            if len(members) != 1:
                raise ExecutionError(
                    "DATASET_CONTRACT_REQUIRED",
                    "ZIP requires exactly one risk_dataset_contract.json",
                )
            member = members[0]
            relative = PurePosixPath(member.filename)
            if (
                relative.is_absolute()
                or len(relative.parts) > 2
                or ".." in relative.parts
                or "\\" in member.filename
            ):
                raise ValueError("Contract must be at the dataset root")
            if member.file_size > 65536 or member.flag_bits & 1:
                raise ValueError("Contract is too large or encrypted")
            value = json.loads(archive.read(member))
        Draft202012Validator(dataset_schema()).validate(value)
        return value
    except (BadZipFile, ValueError, ValidationError) as error:
        raise ExecutionError("DATASET_CONTRACT_INVALID", str(error)) from error
