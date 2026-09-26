import json
from pathlib import Path

import numpy as np
from com_risk_runtime.schema import Dataset


def fit_preprocessor(data: Dataset) -> dict:
    # No validation/test features participate in fitting imputation or scaling.
    raw = np.array([n.features for n in data.nodes if n.split == "train"], dtype=float)
    if not len(raw):
        raise ValueError("no training rows")
    median = np.array(
        [np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0 for col in raw.T]
    )
    clean = np.where(np.isnan(raw), median, raw)
    std = clean.std(0)
    return {
        "median": median.tolist(),
        "mean": clean.mean(0).tolist(),
        "std": np.where(std < 1e-8, 1, std).tolist(),
    }


def dump_json(path: str | Path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
