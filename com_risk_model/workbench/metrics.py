from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def select_threshold(target: np.ndarray, probability: np.ndarray) -> float:
    candidates = np.unique(np.concatenate(([0.0], probability, [1.0])))
    scores = [
        f1_score(target, probability >= threshold, zero_division=0)
        for threshold in candidates
    ]
    return float(candidates[int(np.argmax(scores))])


def evaluate(target: np.ndarray, probability: np.ndarray, threshold: float) -> dict[str, Any]:
    prediction = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(target, prediction, labels=[0, 1]).ravel()
    false_positive_rate, true_positive_rate, _ = roc_curve(target, probability)
    calibration = []
    for index in range(10):
        lower = index / 10
        upper = (index + 1) / 10
        mask = (probability >= lower) & (
            probability <= upper if index == 9 else probability < upper
        )
        if mask.any():
            calibration.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "count": int(mask.sum()),
                    "meanPrediction": float(probability[mask].mean()),
                    "observedRate": float(target[mask].mean()),
                }
            )
    return {
        "rows": len(target),
        "positives": int(target.sum()),
        "rocAuc": float(roc_auc_score(target, probability)),
        "prAuc": float(average_precision_score(target, probability)),
        "ks": float(np.max(true_positive_rate - false_positive_rate)),
        "brier": float(brier_score_loss(target, probability)),
        "precision": float(precision_score(target, prediction, zero_division=0)),
        "recall": float(recall_score(target, prediction, zero_division=0)),
        "f1": float(f1_score(target, prediction, zero_division=0)),
        "threshold": threshold,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration": calibration,
    }
