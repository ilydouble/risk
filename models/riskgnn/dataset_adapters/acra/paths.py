from pathlib import Path


def data_root(directory: Path) -> Path:
    candidates = list(directory.glob("company_attr.parquet"))
    candidates += list(directory.glob("*/company_attr.parquet"))
    if len(candidates) != 1:
        raise ValueError("Expected one ACRA dataset directory")
    return candidates[0].parent
