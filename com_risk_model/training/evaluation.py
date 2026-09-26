"""Offline metrics and validation threshold selection; never imported by the API."""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def metrics(y, p, threshold=0.5):
    y, p = np.asarray(y), np.asarray(p)
    both = len(np.unique(y)) == 2
    fpr, tpr, _ = roc_curve(y, p) if both else (None, None, None)
    pred = p >= threshold
    order = np.argsort(-p, kind="stable")
    k10, k5 = max(1, int(np.ceil(len(y) * 0.1))), max(1, int(np.ceil(len(y) * 0.05)))
    bins = []
    for i in range(10):
        mask = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        if mask.any():
            bins.append(
                {
                    "lower": i / 10,
                    "count": int(mask.sum()),
                    "mean_prediction": float(p[mask].mean()),
                    "observed_rate": float(y[mask].mean()),
                }
            )
    return {
        "n": len(y),
        "positives": int(np.sum(y)),
        "threshold": float(threshold),
        "roc_auc": float(roc_auc_score(y, p)) if both else None,
        "pr_auc": float(average_precision_score(y, p)) if both else None,
        "ks": float(np.max(tpr - fpr)) if tpr is not None and fpr is not None else None,
        "brier": float(brier_score_loss(y, p)),
        "lift_at_10pct": float(y[order[:k10]].mean() / y.mean()) if y.sum() else None,
        "capture_at_5pct": float(y[order[:k5]].sum() / y.sum()) if y.sum() else None,
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "calibration_curve": bins,
    }


def select_threshold(y, p):
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[np.argmax(f1)])
