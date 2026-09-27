from __future__ import annotations

import csv
import io
import math
import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from torch import nn

MAX_ROWS = 20_000
MAX_COLUMNS = 100
MAX_FEATURES = 20
MISSING = {"", "na", "n/a", "null", "none", "nan"}


class AnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCsv:
    columns: list[str]
    rows: list[list[str]]


def _missing(value: str) -> bool:
    return value.strip().casefold() in MISSING


def _number(value: str) -> float | None:
    if _missing(value):
        return None
    try:
        parsed = float(value.replace(",", ""))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_csv(payload: bytes) -> ParsedCsv:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise AnalysisError("CSV must use UTF-8 encoding") from error
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise AnalysisError("CSV header is missing or invalid") from error
    columns = [value.strip() for value in header]
    if not columns or any(not value for value in columns):
        raise AnalysisError("CSV column names must be non-empty")
    if len(columns) != len(set(columns)):
        raise AnalysisError("CSV column names must be unique")
    if len(columns) > MAX_COLUMNS:
        raise AnalysisError(f"CSV supports at most {MAX_COLUMNS} columns")
    rows: list[list[str]] = []
    try:
        for line, row in enumerate(reader, start=2):
            if not any(value.strip() for value in row):
                continue
            if len(row) != len(columns):
                raise AnalysisError(f"CSV row {line} has a different column count")
            rows.append([value.strip() for value in row])
            if len(rows) > MAX_ROWS:
                raise AnalysisError(f"CSV supports at most {MAX_ROWS} data rows")
    except csv.Error as error:
        raise AnalysisError("CSV rows are invalid") from error
    if len(rows) < 10:
        raise AnalysisError("CSV requires at least 10 non-empty data rows")
    return ParsedCsv(columns, rows)


def analyze_csv(payload: bytes) -> tuple[dict[str, Any], list[dict[str, str]]]:
    parsed = parse_csv(payload)
    column_profiles: list[dict[str, Any]] = []
    target_candidates: list[dict[str, Any]] = []
    missing_cells = 0
    for index, name in enumerate(parsed.columns):
        values = [row[index] for row in parsed.rows]
        present = [value for value in values if not _missing(value)]
        missing_count = len(values) - len(present)
        missing_cells += missing_count
        unique = list(dict.fromkeys(present))
        numeric = [_number(value) for value in present]
        is_numeric = bool(present) and all(value is not None for value in numeric)
        if is_numeric:
            numbers = np.asarray(numeric, dtype=float)
            kind = "numeric"
            numeric_stats: dict[str, float] | None = {
                "min": float(numbers.min()),
                "max": float(numbers.max()),
                "mean": float(numbers.mean()),
                "std": float(numbers.std()),
            }
        else:
            kind = "categorical" if len(unique) <= min(100, max(2, len(present) // 2)) else "text"
            numeric_stats = None
        profile = {
            "name": name,
            "kind": kind,
            "missingCount": missing_count,
            "missingRate": missing_count / len(values),
            "uniqueCount": len(unique),
            "samples": unique[:3],
            "numeric": numeric_stats,
        }
        column_profiles.append(profile)
        if len(unique) == 2 and missing_count <= len(values) // 2:
            target_candidates.append({"name": name, "values": unique})
    duplicate_rows = len(parsed.rows) - len({tuple(row) for row in parsed.rows})
    total_cells = len(parsed.rows) * len(parsed.columns)
    warnings: list[str] = []
    if missing_cells / total_cells > 0.2:
        warnings.append("missing_rate_high")
    if duplicate_rows:
        warnings.append("duplicate_rows")
    if not target_candidates:
        warnings.append("no_binary_target")
    analysis = {
        "rowCount": len(parsed.rows),
        "columnCount": len(parsed.columns),
        "missingCells": missing_cells,
        "missingRate": missing_cells / total_cells,
        "duplicateRows": duplicate_rows,
        "numericColumnCount": sum(column["kind"] == "numeric" for column in column_profiles),
        "categoricalColumnCount": sum(
            column["kind"] == "categorical" for column in column_profiles
        ),
        "columns": column_profiles,
        "targetCandidates": target_candidates,
        "warnings": warnings,
    }
    preview = [
        {name: value[:200] for name, value in zip(parsed.columns, row, strict=True)}
        for row in parsed.rows[:8]
    ]
    return analysis, preview


def _stratified_split(labels: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = random.Random(seed)
    train: list[int] = []
    test: list[int] = []
    for value in (0, 1):
        indices = np.where(labels == value)[0].tolist()
        if len(indices) < 5:
            raise AnalysisError("Each target class requires at least 5 rows")
        rng.shuffle(indices)
        test_count = max(1, round(len(indices) * 0.2))
        test.extend(indices[:test_count])
        train.extend(indices[test_count:])
    rng.shuffle(train)
    rng.shuffle(test)
    return np.asarray(train), np.asarray(test)


def _auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = int(labels.sum())
    negatives = len(labels) - positives
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(len(scores), dtype=float)
    start = 0
    while start < len(scores):
        end = start + 1
        while end < len(scores) and scores[order[end]] == scores[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2
        start = end
    rank_sum = float(ranks[labels == 1].sum())
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    order = np.argsort(-scores, kind="stable")
    ordered = labels[order]
    cumulative = np.cumsum(ordered)
    precision = cumulative / np.arange(1, len(labels) + 1)
    return float(precision[ordered == 1].mean())


def _metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    predictions = scores >= 0.5
    tp = int(np.sum((predictions == 1) & (labels == 1)))
    fp = int(np.sum((predictions == 1) & (labels == 0)))
    tn = int(np.sum((predictions == 0) & (labels == 0)))
    fn = int(np.sum((predictions == 0) & (labels == 1)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    positive_scores = np.sort(scores[labels == 1])
    negative_scores = np.sort(scores[labels == 0])
    thresholds = np.unique(scores)
    ks = max(
        abs(
            np.searchsorted(positive_scores, threshold, side="right") / len(positive_scores)
            - np.searchsorted(negative_scores, threshold, side="right") / len(negative_scores)
        )
        for threshold in thresholds
    )
    calibration = []
    for index in range(10):
        low, high = index / 10, (index + 1) / 10
        mask = (scores >= low) & (scores < high if index < 9 else scores <= high)
        if mask.any():
            calibration.append(
                {
                    "lower": low,
                    "count": int(mask.sum()),
                    "meanPrediction": float(scores[mask].mean()),
                    "observedRate": float(labels[mask].mean()),
                }
            )
    return {
        "rows": len(labels),
        "positives": int(labels.sum()),
        "rocAuc": _auc(labels, scores),
        "prAuc": _average_precision(labels, scores),
        "ks": float(ks),
        "brier": float(np.mean((scores - labels) ** 2)),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "threshold": 0.5,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "calibration": calibration,
    }


def train_baseline(
    payload: bytes,
    target_column: str,
    positive_value: str,
    feature_columns: list[str],
    seed: int,
) -> dict[str, Any]:
    parsed = parse_csv(payload)
    if target_column not in parsed.columns:
        raise AnalysisError("Target column does not exist")
    if not feature_columns or len(feature_columns) > MAX_FEATURES:
        raise AnalysisError(f"Select between 1 and {MAX_FEATURES} feature columns")
    if len(feature_columns) != len(set(feature_columns)) or target_column in feature_columns:
        raise AnalysisError("Feature columns must be unique and exclude the target")
    if any(column not in parsed.columns for column in feature_columns):
        raise AnalysisError("A feature column does not exist")
    target_index = parsed.columns.index(target_column)
    feature_indices = [parsed.columns.index(column) for column in feature_columns]
    usable = [row for row in parsed.rows if not _missing(row[target_index])]
    target_values = list(dict.fromkeys(row[target_index] for row in usable))
    if len(target_values) != 2 or positive_value not in target_values:
        raise AnalysisError("Target must contain exactly two values and include the positive value")
    matrix: list[list[float]] = []
    labels: list[int] = []
    for row in usable:
        values = [_number(row[index]) for index in feature_indices]
        pairs = zip(feature_indices, values, strict=True)
        if any(not _missing(row[index]) and value is None for index, value in pairs):
            raise AnalysisError("All selected features must be numeric")
        matrix.append([float("nan") if value is None else value for value in values])
        labels.append(int(row[target_index] == positive_value))
    x = np.asarray(matrix, dtype=np.float32)
    y = np.asarray(labels, dtype=np.int64)
    train_indices, test_indices = _stratified_split(y, seed)
    medians = np.nanmedian(x[train_indices], axis=0)
    if np.isnan(medians).any():
        raise AnalysisError("A selected feature is completely missing in training data")
    clean = np.where(np.isnan(x), medians, x)
    means = clean[train_indices].mean(axis=0)
    stds = clean[train_indices].std(axis=0)
    stds = np.where(stds < 1e-8, 1.0, stds)
    clean = np.clip((clean - means) / stds, -10, 10).astype(np.float32)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    model = nn.Linear(len(feature_columns), 1)
    with torch.no_grad():
        model.weight.zero_()
        model.bias.zero_()
    optimizer = torch.optim.LBFGS(model.parameters(), max_iter=100, line_search_fn="strong_wolfe")
    train_x = torch.tensor(clean[train_indices])
    train_y = torch.tensor(y[train_indices], dtype=torch.float32)

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        loss = nn.functional.binary_cross_entropy_with_logits(
            model(train_x).squeeze(-1), train_y
        )
        loss.backward()
        return loss

    optimizer.step(closure)
    with torch.no_grad():
        probabilities = model(torch.tensor(clean)).squeeze(-1).sigmoid().numpy()
    coefficients: list[dict[str, Any]] = [
        {"feature": feature, "coefficient": float(value)}
        for feature, value in zip(
            feature_columns, model.weight.detach().numpy().reshape(-1), strict=True
        )
    ]
    coefficients.sort(key=lambda row: abs(row["coefficient"]), reverse=True)
    return {
        "configuration": {
            "seed": seed,
            "split": "stratified_random_holdout_80_20",
            "evaluationScope": "quick_baseline_not_temporal_validation",
            "trainRows": len(train_indices),
            "testRows": len(test_indices),
            "negativeValue": next(value for value in target_values if value != positive_value),
        },
        "metrics": {
            "train": _metrics(y[train_indices], probabilities[train_indices]),
            "test": _metrics(y[test_indices], probabilities[test_indices]),
        },
        "coefficients": coefficients,
    }
