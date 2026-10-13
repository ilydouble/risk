"""Post-hoc recalibration and risk--coverage triage analysis.

Motivation
----------
Class-weighted training on a 3.4%-positive graph makes every arm systematically
over-predict defaults, so *any* metric that thresholds a raw probability at 0.5
(accuracy, Brier, "auto-decision error rate") is confounded by miscalibration:
on the UK test split the raw Brier score (0.132--0.148) is worse than a constant
base-rate predictor (0.033).  Reviewers will exploit exactly this.

Two fixes, applied identically to every arm:

1. **Monotone recalibration** on the held-out calibration split (isotonic by
   default). Isotonic steps create ties that can alter AP and review ranking.
2. **Risk--coverage curves** for triage.  Instead of a single thresholded error
   rate, we sweep the human-review budget, defer the most suspicious cases, and
   measure the selective risk of the auto-processed remainder. AURC integrates
   over review budgets; the class decision still uses a 0.5 threshold.

The deferral signal is what differs across methods:

* ``softmax``   : ambiguity ``0.5 - |p - 0.5|``
* ``naive_edl`` : Dirichlet uncertainty ``u``
* ``tacr``      : legacy output key for ambiguity ``+ gamma * conflict``. This
  ranking score differs from the TACR conformal nonconformity score. ``gamma``
  is tuned on the calibration split only (never on test).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

DEFAULT_GAMMAS = (0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0)
DEFAULT_COVERAGES = (0.5, 0.6, 0.7, 0.8, 0.9)


@dataclass
class Recalibrator:
    """Monotone post-hoc probability recalibrator fit on a calibration split."""

    method: str = "isotonic"

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> Recalibrator:
        p = np.asarray(probabilities, dtype=np.float64)
        y = np.asarray(labels, dtype=np.int64)
        if self.method == "isotonic":
            self._model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self._model.fit(p, y)
        elif self.method == "platt":
            # Logistic regression on the log-odds; safer when the calibration set
            # is small (SMEsD has only ~360 calibration points).
            logit = np.log(
                np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))
            )
            self._model = LogisticRegression(C=1.0, solver="lbfgs")
            self._model.fit(logit.reshape(-1, 1), y)
        else:
            raise ValueError(f"unknown recalibration method: {self.method}")
        return self

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        p = np.asarray(probabilities, dtype=np.float64)
        if self.method == "isotonic":
            return np.clip(self._model.predict(p), 0.0, 1.0)
        logit = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
        return self._model.predict_proba(logit.reshape(-1, 1))[:, 1]


def _risk_curve(
    suspicion: np.ndarray, decisions: np.ndarray, labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Selective risk as a function of coverage.

    Returns ``(coverage, risk)`` sorted by ascending coverage, where coverage is
    the fraction of samples kept automatically after deferring the most
    suspicious ones.  ``suspicion`` is oriented so that larger values are
    deferred first.
    """
    n = len(labels)
    order = np.argsort(-np.asarray(suspicion, dtype=np.float64), kind="mergesort")
    errors = (np.asarray(decisions)[order] != np.asarray(labels)[order]).astype(
        np.float64
    )
    cumulative = np.concatenate(([0.0], np.cumsum(errors)))
    total = cumulative[-1]

    # Defer k = 0..n-1 samples; the remaining n - k are auto-processed.
    ks = np.arange(0, n)
    auto_n = n - ks
    auto_err = total - cumulative[ks]
    risk = auto_err / auto_n
    coverage = auto_n / n
    ascending = np.argsort(coverage)
    return coverage[ascending], risk[ascending]


def aurc(suspicion: np.ndarray, decisions: np.ndarray, labels: np.ndarray) -> float:
    """Area under the risk--coverage curve (lower is better)."""
    coverage, risk = _risk_curve(suspicion, decisions, labels)
    # Coverage starts at 1/n, so prepend the full-deferral point for a [0, 1] integral.
    coverage = np.concatenate(([0.0], coverage))
    risk = np.concatenate(([risk[0]], risk))
    return float(np.trapezoid(risk, coverage))


def risk_at_coverage(
    suspicion: np.ndarray, decisions: np.ndarray, labels: np.ndarray, coverage: float
) -> float:
    """Selective risk when exactly ``coverage`` of samples are auto-processed."""
    cov, risk = _risk_curve(suspicion, decisions, labels)
    return float(np.interp(coverage, cov, risk))


def missed_default_rate(
    suspicion: np.ndarray,
    calibrated_p: np.ndarray,
    labels: np.ndarray,
    coverage: float,
) -> float:
    """Default rate among auto-*approved* firms at a given auto-coverage.

    This is the economically meaningful quantity: of the loans we approve
    without a human, how many actually default?  Lower is better.
    """
    n = len(labels)
    defer = round(n * (1.0 - coverage))
    order = np.argsort(-np.asarray(suspicion, dtype=np.float64), kind="mergesort")
    keep = np.ones(n, dtype=bool)
    keep[order[:defer]] = False
    approved = keep & (np.asarray(calibrated_p) < 0.5)
    if approved.sum() == 0:
        return 0.0
    return float(np.asarray(labels)[approved].mean())


def tune_gamma(
    cal_p: np.ndarray,
    cal_conflict: np.ndarray,
    cal_y: np.ndarray,
    gammas: tuple[float, ...] = DEFAULT_GAMMAS,
    target_coverage: float = 0.7,
) -> float:
    """Choose the conflict weight that minimises calibration-split selective risk.

    Tuning excludes test labels. The same calibration labels also fit the
    probability map, so separate calibration/tuning splits would be stronger.
    """
    ambiguity = 0.5 - np.abs(np.asarray(cal_p, dtype=np.float64) - 0.5)
    decisions = (np.asarray(cal_p, dtype=np.float64) >= 0.5).astype(np.int64)
    best_gamma, best_risk = 0.0, float("inf")
    for gamma in gammas:
        suspicion = ambiguity + gamma * np.asarray(cal_conflict, dtype=np.float64)
        risk = risk_at_coverage(suspicion, decisions, cal_y, target_coverage)
        if risk < best_risk - 1e-12:
            best_gamma, best_risk = float(gamma), risk
    return best_gamma


def evaluate_triage(
    test_p: np.ndarray,
    test_u: np.ndarray,
    test_conflict: np.ndarray,
    test_y: np.ndarray,
    gamma: float,
    coverages: tuple[float, ...] = DEFAULT_COVERAGES,
) -> dict[str, dict[str, float]]:
    """Evaluate the three triage signals on one test split.

    ``test_p`` must already be recalibrated, so the 0.5 decision boundary is
    meaningful for every method.
    """
    p = np.asarray(test_p, dtype=np.float64)
    decisions = (p >= 0.5).astype(np.int64)
    ambiguity = 0.5 - np.abs(p - 0.5)

    signals = {
        "softmax": ambiguity,
        "naive_edl": np.asarray(test_u, dtype=np.float64),
        "tacr": ambiguity + gamma * np.asarray(test_conflict, dtype=np.float64),
    }

    out: dict[str, dict[str, float]] = {}
    for name, suspicion in signals.items():
        row = {"aurc": aurc(suspicion, decisions, test_y)}
        for coverage in coverages:
            row[f"risk@{coverage:.1f}"] = risk_at_coverage(
                suspicion, decisions, test_y, coverage
            )
            row[f"missed@{coverage:.1f}"] = missed_default_rate(
                suspicion, p, test_y, coverage
            )
        out[name] = row
    return out
