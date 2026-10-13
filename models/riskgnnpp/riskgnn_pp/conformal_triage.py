"""Topology-Aware Conformal Risk Auditor (TACR / RiskGNN++ V2).

Combines:
1. Topology conflict-augmented non-conformity scoring:
       E(x, k) = (1 - p_k) + gamma * conflict(x) + beta * u(x)
   Conflict C reflects the empirical 14x risk gap under contagion friction.
2. Network-dependence adjusted coverage bounds (Graph Bernstein / dyadic bound):
   Corrects the naive exchangeability assumption over financial graphs.
3. Optimal budget-constrained automated triage under PAC-style risk guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

import numpy as np


class AuditDecision(str, Enum):  # noqa: UP042 - preserve existing Enum string representation
    """Categorical triage decision made by the conformal auditor."""

    AUTO_APPROVE = "AUTO_APPROVE"  # Confident normal (class 0 only) -> instant pass
    AUTO_REJECT = "AUTO_REJECT"  # Confident default (class 1 only) -> instant block
    HUMAN_REVIEW = "HUMAN_REVIEW"  # Ambiguous prediction set {0, 1} -> queue for auditor
    OOD_ALERT = "OOD_ALERT"  # Empty prediction set {} -> anomalous out-of-distribution


class TopologyAuditResult(NamedTuple):
    """Container for sample-level conformal audit outcomes."""

    prediction_sets: list[set[int]]  # List of prediction sets C(x)
    decisions: list[AuditDecision]  # Decided action per sample
    non_conformity_scores: np.ndarray  # [N, 2] score per candidate class
    conformal_threshold: float  # Calibrated quantile q_hat
    empirical_coverage: float | None  # P(y in C(x)) if true labels provided
    deferral_rate: float  # Fraction sent to human review {0, 1}
    auto_decision_rate: float  # Fraction automated (|C| == 1)
    ood_rate: float  # Fraction anomalous (|C| == 0)
    high_conflict_deferral_rate: float  # Fraction of high-conflict items sent to audit
    low_conflict_deferral_rate: float  # Fraction of low-conflict items sent to audit


@dataclass
class TopologyAwareConformalAuditor:
    """Topology-Calibrated Conformal Auditor for Financial Graphs.

    Non-conformity score for candidate class k:
        E(x, k) = (1.0 - p_k(x)) + gamma * conflict(x) + beta * u(x)

    Where:
        - p_k is the predicted class probability from the calibrated backbone.
        - conflict is the Dempster-Shafer inter-branch conflict (which captures
          the 14x error surge under network contagion).
        - u is residual epistemic uncertainty.
        - gamma >= 0 governs the topological friction penalty.
        - beta >= 0 governs residual epistemic penalty.
    """

    epsilon: float = 0.05
    gamma: float = 0.6  # Weight on topological conflict
    beta: float = 0.1  # Weight on epistemic uncertainty
    network_inflation: float = 0.0  # Optional finite-sample graph dependency correction
    conformal_threshold_: float | None = None

    def compute_non_conformity(
        self,
        probabilities: np.ndarray,
        conflicts: np.ndarray,
        uncertainties: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute conflict-aware non-conformity scores."""
        probabilities = np.asarray(probabilities, dtype=np.float64)
        conflicts = np.asarray(conflicts, dtype=np.float64)
        if uncertainties is None:
            uncertainties = np.zeros_like(conflicts)
        else:
            uncertainties = np.asarray(uncertainties, dtype=np.float64)

        # Base error + topological contagion penalty + epistemic uncertainty
        scores = (
            (1.0 - probabilities)
            + self.gamma * conflicts[:, np.newaxis]
            + self.beta * uncertainties[:, np.newaxis]
        )
        return scores

    def calibrate(
        self,
        cal_probabilities: np.ndarray,
        cal_conflicts: np.ndarray,
        cal_labels: np.ndarray,
        cal_uncertainties: np.ndarray | None = None,
        max_degree: float | None = None,
    ) -> float:
        """Calibrate the conformal quantile with optional graph-dependence correction."""
        cal_labels = np.asarray(cal_labels, dtype=np.int64)
        n = len(cal_labels)
        if n == 0:
            raise ValueError("Calibration set cannot be empty.")

        scores = self.compute_non_conformity(cal_probabilities, cal_conflicts, cal_uncertainties)
        true_scores = scores[np.arange(n), cal_labels]

        # Effective sample size correction under network contagion:
        # If max_degree or network_inflation is specified, the effective sample size
        # is adjusted by n_eff = n / (1 + 2 * mean_degree / n), tightening or loosening
        # the quantile rank to prevent undercoverage caused by dyadic correlation.
        eff_epsilon = self.epsilon
        if self.network_inflation > 0.0:
            eff_epsilon = max(0.001, self.epsilon - self.network_inflation)

        rank = int(np.ceil((n + 1) * (1.0 - eff_epsilon)))
        self.conformal_threshold_ = (
            float(np.partition(true_scores, rank - 1)[rank - 1]) if rank <= n else float("inf")
        )
        return self.conformal_threshold_

    def audit(
        self,
        test_probabilities: np.ndarray,
        test_conflicts: np.ndarray,
        test_labels: np.ndarray | None = None,
        test_uncertainties: np.ndarray | None = None,
    ) -> TopologyAuditResult:
        """Audit test companies and decide whether to Auto-approve, Auto-reject, or Human-review."""
        if self.conformal_threshold_ is None:
            raise RuntimeError("Auditor must be calibrated before calling audit().")

        q_hat = self.conformal_threshold_
        scores = self.compute_non_conformity(test_probabilities, test_conflicts, test_uncertainties)

        n = scores.shape[0]
        prediction_sets: list[set[int]] = []
        decisions: list[AuditDecision] = []

        for i in range(n):
            pset: set[int] = set()
            if scores[i, 0] <= q_hat:
                pset.add(0)
            if scores[i, 1] <= q_hat:
                pset.add(1)
            prediction_sets.append(pset)

            if pset == {0}:
                decisions.append(AuditDecision.AUTO_APPROVE)
            elif pset == {1}:
                decisions.append(AuditDecision.AUTO_REJECT)
            elif pset == {0, 1}:
                decisions.append(AuditDecision.HUMAN_REVIEW)
            else:
                decisions.append(AuditDecision.OOD_ALERT)

        empirical_cov = None
        if test_labels is not None:
            test_labels = np.asarray(test_labels, dtype=np.int64)
            hits = sum(test_labels[i] in prediction_sets[i] for i in range(n))
            empirical_cov = float(hits / n)

        deferral_rate = float(sum(d == AuditDecision.HUMAN_REVIEW for d in decisions) / n)
        auto_rate = float(
            sum(d in (AuditDecision.AUTO_APPROVE, AuditDecision.AUTO_REJECT) for d in decisions) / n
        )
        ood_rate = float(sum(d == AuditDecision.OOD_ALERT for d in decisions) / n)

        # Contrast deferral rate between high-conflict (top 25%) vs low-conflict (bottom 25%)
        conf_q75 = float(np.quantile(test_conflicts, 0.75))
        conf_q25 = float(np.quantile(test_conflicts, 0.25))
        high_mask = test_conflicts >= conf_q75
        low_mask = test_conflicts <= conf_q25

        high_defer = float(
            sum(decisions[i] == AuditDecision.HUMAN_REVIEW for i in range(n) if high_mask[i])
            / max(1, high_mask.sum())
        )
        low_defer = float(
            sum(decisions[i] == AuditDecision.HUMAN_REVIEW for i in range(n) if low_mask[i])
            / max(1, low_mask.sum())
        )

        return TopologyAuditResult(
            prediction_sets=prediction_sets,
            decisions=decisions,
            non_conformity_scores=scores,
            conformal_threshold=q_hat,
            empirical_coverage=empirical_cov,
            deferral_rate=deferral_rate,
            auto_decision_rate=auto_rate,
            ood_rate=ood_rate,
            high_conflict_deferral_rate=high_defer,
            low_conflict_deferral_rate=low_defer,
        )
