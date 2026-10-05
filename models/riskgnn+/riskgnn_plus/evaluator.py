"""Evaluation tools for RiskGNN+: ROC, PR-AUC, ECE, Conflict analysis, and Deferral."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def expected_calibration_error(
    probabilities: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Calculate Expected Calibration Error (ECE).

    Args:
        probabilities: [N] predicted default probabilities.
        labels: [N] binary labels (0 or 1).
        n_bins: Number of probability bins.

    Returns:
        ECE scalar in [0, 1].
    """
    probabilities = np.asarray(probabilities, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(probabilities, bins) - 1

    ece = 0.0
    n = len(labels)
    for b in range(n_bins):
        mask = bin_indices == b
        if np.sum(mask) > 0:
            bin_acc = np.mean(labels[mask])
            bin_conf = np.mean(probabilities[mask])
            bin_weight = np.sum(mask) / n
            ece += bin_weight * np.abs(bin_acc - bin_conf)
    return float(ece)


def evaluate_risk_predictions(
    probabilities: np.ndarray,
    labels: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compute comprehensive classification performance metrics."""
    probabilities = np.asarray(probabilities, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    predictions = (probabilities >= threshold).astype(int)

    return {
        "rocAuc": float(roc_auc_score(labels, probabilities)),
        "prAuc": float(average_precision_score(labels, probabilities)),
        "ece": expected_calibration_error(probabilities, labels),
        "brier": float(brier_score_loss(labels, probabilities)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
    }


def analyze_conflict_contagion(
    conflicts: np.ndarray,
    labels: np.ndarray,
    quantiles: int = 4,
) -> list[dict[str, float]]:
    """Analyze empirical default rate across different inter-branch conflict strata.

    Validates whether high conflict C between Node and Graph corresponds to higher risk.
    """
    conflicts = np.asarray(conflicts, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)

    bins = np.quantile(conflicts, np.linspace(0, 1, quantiles + 1))
    results = []

    for i in range(quantiles):
        low, high = bins[i], bins[i + 1]
        if i == quantiles - 1:
            mask = (conflicts >= low) & (conflicts <= high)
        else:
            mask = (conflicts >= low) & (conflicts < high)

        count = int(np.sum(mask))
        default_rate = float(np.mean(labels[mask])) if count > 0 else 0.0
        results.append({
            "stratum": i + 1,
            "conflict_min": float(low),
            "conflict_max": float(high),
            "sample_count": count,
            "default_rate": default_rate,
        })
    return results
