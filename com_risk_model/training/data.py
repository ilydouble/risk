import json
from pathlib import Path

from com_risk_runtime.schema import Dataset


def load_data(path):
    path = Path(path)
    if path.is_dir():
        return {s: Dataset.read(path / f"{s}.json") for s in ("train", "valid", "test")}
    return Dataset.read(path)


def dump_json(path: str | Path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
