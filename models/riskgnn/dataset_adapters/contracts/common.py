import json
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1)]
Count = Annotated[int, Field(ge=0)]


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def finite_json(self):
        # JsonValue extension fields must obey the same finite-number contract as core fields.
        json.dumps(self.model_dump(mode="python"), allow_nan=False)
        return self


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        raise ValueError("Expected a workspace-relative POSIX path")
    return value
