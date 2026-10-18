"""Paths shared by research CLI execution and deployed inference."""

from os import getenv
from pathlib import Path


def model_root() -> Path:
    return Path(getenv("MODEL_CODE_ROOT", str(Path(__file__).resolve().parents[4])))
