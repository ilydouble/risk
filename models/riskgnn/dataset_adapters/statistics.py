"""Statistics shared by dataset-specific reports."""

from typing import Any

import numpy as np
import pandas as pd


def safe_number(value: Any) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def psi(train: pd.Series, other: pd.Series) -> float:
    if pd.api.types.is_numeric_dtype(train):
        clean = pd.to_numeric(train, errors="coerce").dropna()
        if clean.nunique() > 1:
            edges = np.unique(np.quantile(clean, np.linspace(0, 1, 11)))
            if len(edges) > 2:
                train_bins = pd.cut(
                    pd.to_numeric(train, errors="coerce"), edges, include_lowest=True
                )
                other_bins = pd.cut(
                    pd.to_numeric(other, errors="coerce"), edges, include_lowest=True
                )
            else:
                train_bins, other_bins = train.astype(str), other.astype(str)
        else:
            train_bins, other_bins = train.astype(str), other.astype(str)
    else:
        train_bins, other_bins = train.astype(str), other.astype(str)
    left = pd.Series(train_bins).astype("string").fillna("__MISSING__").value_counts(normalize=True)
    right = (
        pd.Series(other_bins).astype("string").fillna("__MISSING__").value_counts(normalize=True)
    )
    categories = left.index.union(right.index)
    expected = left.reindex(categories, fill_value=0).clip(lower=1e-6)
    actual = right.reindex(categories, fill_value=0).clip(lower=1e-6)
    return float(((actual - expected) * np.log(actual / expected)).sum())
