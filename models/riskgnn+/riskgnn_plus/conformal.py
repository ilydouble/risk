"""Inductive Conformal Prediction (ICP) Auditor for RiskGNN+.

Provides mathematically guaranteed error bounds, selective classification,
automated approval/rejection, and routing of ambiguous cases to human credit auditors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

import numpy as np


class AuditDecision(str, Enum):
    """Categorical triage decision made by the conformal auditor."""

    AUTO_APPROVE = "AUTO_APPROVE"   # Confident normal (class 0 only) -> instant pass
    AUTO_REJECT = "AUTO_REJECT"     # Confident default (class 1 only) -> instant block
    HUMAN_REVIEW = "HUMAN_REVIEW"   # Ambiguous prediction set {0, 1} -> queue for auditor
    OOD_ALERT = "OOD_ALERT"         # Empty prediction set {} -> anomalous out-of-distribution


class AuditResult(NamedTuple):
    """Container for sample-level conformal audit outcomes."""

    prediction_sets: list[set[int]]       # List of prediction sets C(x)
    decisions: list[AuditDecision]        # Decided action per sample
    non_conformity_scores: np.ndarray    # [N, 2] score per candidate class
    conformal_threshold: float           # Calibrated quantile q_hat
    empirical_coverage: float | None     # P(y in C(x)) if true labels provided
    deferral_rate: float                 # Fraction sent to human review {0, 1}
    auto_decision_rate: float            # Fraction automated (|C| == 1)
    ood_rate: float                      # Fraction anomalous (|C| == 0)


@dataclass
class ConformalRiskAuditor:
    """Inductive Conformal Prediction Auditor for Default Risk.

    Non-conformity score for candidate class k:
        E(x, k) = 1.0 - p_k(x) + beta * u(x)

    Where:
        - p_k is the predicted probability of class k.
        - u is the epistemic uncertainty from DST fusion.
        - beta >= 0 governs the uncertainty penalty.

    Mathematical guarantee:
        For significance level epsilon in (0, 1), the true label y satisfies:
        P(y in C(x)) >= 1.0 - epsilon
    """

    epsilon: float = 0.05       # Target error rate (e.g. 0.05 -> 95% guaranteed coverage)
    beta: float = 0.5           # Epistemic uncertainty penalty factor
    conformal_threshold_: float | None = None

    def compute_non_conformity(
        self,
        probabilities: np.ndarray,
        uncertainties: np.ndarray,
    ) -> np.ndarray:
        """Compute non-conformity scores E for both classes (0 and 1).

        Args:
            probabilities: [N, 2] array of probabilities [p_normal, p_default].
            uncertainties: [N] array of epistemic uncertainties u in [0, 1].

        Returns:
            [N, 2] array where column 0 is E(x, 0) and column 1 is E(x, 1).
        """
        probabilities = np.asarray(probabilities, dtype=np.float64)
        uncertainties = np.asarray(uncertainties, dtype=np.float64)
        # E(x, k) = 1 - p_k + beta * u
        scores = (1.0 - probabilities) + self.beta * uncertainties[:, np.newaxis]
        return scores

    def calibrate(
        self,
        cal_probabilities: np.ndarray,
        cal_uncertainties: np.ndarray,
        cal_labels: np.ndarray,
    ) -> float:
        """Calibrate the conformal threshold q_hat on a holdout calibration set.

        Args:
            cal_probabilities: [N_cal, 2] probabilities on calibration set.
            cal_uncertainties: [N_cal] epistemic uncertainties on calibration set.
            cal_labels: [N_cal] ground-truth binary labels (0 or 1).

        Returns:
            The calibrated quantile threshold q_hat.
        """
        cal_labels = np.asarray(cal_labels, dtype=np.int64)
        n = len(cal_labels)
        if n == 0:
            raise ValueError("Calibration dataset cannot be empty.")

        scores = self.compute_non_conformity(cal_probabilities, cal_uncertainties)
        # Extract the score corresponding to the true label: E_i = scores[i, y_i]
        true_scores = scores[np.arange(n), cal_labels]

        # Conformal quantile: ceil((n + 1) * (1 - epsilon)) / n
        quantile_level = float(np.ceil((n + 1) * (1.0 - self.epsilon)) / n)
        quantile_level = min(1.0, max(0.0, quantile_level))

        # Quantile using method='higher' or standard linear interpolation
        self.conformal_threshold_ = float(np.quantile(true_scores, quantile_level, method="higher"))
        return self.conformal_threshold_

    def audit(
        self,
        test_probabilities: np.ndarray,
        test_uncertainties: np.ndarray,
        test_labels: np.ndarray | None = None,
    ) -> AuditResult:
        """Perform conformal triage audit on test/production enterprise samples.

        Args:
            test_probabilities: [N, 2] test probabilities.
            test_uncertainties: [N] test epistemic uncertainties.
            test_labels: Optional [N] true labels to evaluate empirical coverage.

        Returns:
            AuditResult containing prediction sets, decisions, and triage metrics.
        """
        if self.conformal_threshold_ is None:
            raise RuntimeError("Auditor must be calibrated before calling audit().")

        q_hat = self.conformal_threshold_
        scores = self.compute_non_conformity(test_probabilities, test_uncertainties)

        prediction_sets: list[set[int]] = []
        decisions: list[AuditDecision] = []

        n = len(test_probabilities)
        for i in range(n):
            c_set = set()
            if scores[i, 0] <= q_hat:
                c_set.add(0)
            if scores[i, 1] <= q_hat:
                c_set.add(1)

            prediction_sets.append(c_set)

            if c_set == {0}:
                decisions.append(AuditDecision.AUTO_APPROVE)
            elif c_set == {1}:
                decisions.append(AuditDecision.AUTO_REJECT)
            elif len(c_set) == 2:
                decisions.append(AuditDecision.HUMAN_REVIEW)
            else:
                decisions.append(AuditDecision.OOD_ALERT)

        # Metrics
        empirical_cov = None
        if test_labels is not None:
            test_labels = np.asarray(test_labels, dtype=np.int64)
            covered = [test_labels[i] in prediction_sets[i] for i in range(n)]
            empirical_cov = float(np.mean(covered))

        defer_count = sum(1 for d in decisions if d == AuditDecision.HUMAN_REVIEW)
        auto_count = sum(1 for d in decisions if d in (AuditDecision.AUTO_APPROVE, AuditDecision.AUTO_REJECT))
        ood_count = sum(1 for d in decisions if d == AuditDecision.OOD_ALERT)

        return AuditResult(
            prediction_sets=prediction_sets,
            decisions=decisions,
            non_conformity_scores=scores,
            conformal_threshold=q_hat,
            empirical_coverage=empirical_cov,
            deferral_rate=float(defer_count / n) if n > 0 else 0.0,
            auto_decision_rate=float(auto_count / n) if n > 0 else 0.0,
            ood_rate=float(ood_count / n) if n > 0 else 0.0,
        )
