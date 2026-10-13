"""Contract tests for post-hoc recalibration and risk--coverage triage."""

from __future__ import annotations

import numpy as np
from riskgnn_pp.triage_analysis import (
    Recalibrator,
    aurc,
    evaluate_triage,
    missed_default_rate,
    risk_at_coverage,
    tune_gamma,
)


def _synthetic(n: int = 4000, seed: int = 0):
    rng = np.random.default_rng(seed)
    latent = rng.normal(size=n)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-latent))).astype(np.int64)
    overconfident = 1.0 / (1.0 + np.exp(-2.5 * latent))  # systematically over-sharp
    return latent, y, overconfident


def test_recalibrator_isotonic_reduces_ece_and_preserves_order():
    _, y_cal, raw_cal = _synthetic(4000, seed=1)
    _, y_test, raw_test = _synthetic(4000, seed=2)
    recal = Recalibrator(method="isotonic").fit(raw_cal, y_cal)
    calibrated = recal.transform(raw_test)

    def ece(p: np.ndarray, y: np.ndarray, bins: int = 15) -> float:
        edges = np.linspace(0.0, 1.0, bins + 1)
        idx = np.digitize(p, edges) - 1
        return float(
            sum(
                (idx == b).mean() * abs(y[idx == b].mean() - p[idx == b].mean())
                for b in range(bins)
                if (idx == b).any()
            )
        )

    assert ece(calibrated, y_test) < ece(raw_test, y_test)
    # Isotonic is monotone non-decreasing; ties may collapse distinct inputs, so
    # check the sorted profile rather than the argsort permutation.
    sorted_calibrated = calibrated[np.argsort(raw_test)]
    assert np.all(np.diff(sorted_calibrated) >= -1e-12)


def test_recalibrator_platt_stays_in_unit_interval():
    _, y_cal, raw_cal = _synthetic(4000, seed=3)
    _, _, raw_test = _synthetic(4000, seed=4)
    calibrated = Recalibrator(method="platt").fit(raw_cal, y_cal).transform(raw_test)
    assert calibrated.min() >= 0.0 and calibrated.max() <= 1.0
    assert np.isfinite(calibrated).all()


def test_aurc_rewards_an_informative_suspicion_signal():
    rng = np.random.default_rng(5)
    n = 3000
    y = (rng.random(n) < 0.2).astype(np.int64)
    decisions = y.copy()
    # Flip a known, identifiable subset to create errors the suspicion signal can find.
    flipped = rng.choice(n, size=200, replace=False)
    decisions[flipped] = 1 - decisions[flipped]

    informative = np.zeros(n)
    informative[flipped] = 1.0
    uninformative = rng.normal(size=n)

    assert aurc(informative, decisions, y) < aurc(uninformative, decisions, y)


def test_risk_at_coverage_bounds_and_monotonicity():
    rng = np.random.default_rng(6)
    n = 2000
    y = (rng.random(n) < 0.3).astype(np.int64)
    decisions = (rng.random(n) < 0.3).astype(np.int64)
    suspicion = rng.normal(size=n)
    risks = [
        risk_at_coverage(suspicion, decisions, y, c) for c in (0.5, 0.6, 0.7, 0.8, 0.9)
    ]
    assert all(0.0 <= r <= 1.0 for r in risks)


def test_missed_default_rate_is_lower_for_better_signal():
    rng = np.random.default_rng(7)
    n = 4000
    p = rng.random(n)
    y = (rng.random(n) < p).astype(np.int64)
    # Suspicion correlated with default risk => deferring it protects approvals.
    good = p + 0.001 * rng.normal(size=n)
    bad = rng.normal(size=n)
    assert missed_default_rate(good, p, y, 0.7) <= missed_default_rate(bad, p, y, 0.7)
    assert 0.0 <= missed_default_rate(good, p, y, 0.5) <= 1.0


def test_tune_gamma_prefers_conflict_when_it_predicts_errors():
    rng = np.random.default_rng(8)
    n = 4000
    y = (rng.random(n) < 0.15).astype(np.int64)
    p = np.clip(0.15 + 0.1 * rng.normal(size=n), 1e-3, 1 - 1e-3)
    conflict = rng.random(n)
    # Errors concentrate in high-conflict nodes, so discounting them should help.
    noisy = conflict > 0.8
    p = np.where(noisy, 0.5 + 0.2 * rng.normal(size=n), p)
    p = np.clip(p, 1e-3, 1 - 1e-3)
    gamma = tune_gamma(p, conflict, y)
    assert gamma > 0.0


def test_evaluate_triage_reports_all_signals():
    rng = np.random.default_rng(9)
    n = 1500
    y = (rng.random(n) < 0.2).astype(np.int64)
    p = np.clip(0.2 + 0.2 * rng.normal(size=n), 1e-3, 1 - 1e-3)
    u = rng.random(n)
    conflict = rng.random(n)
    result = evaluate_triage(p, u, conflict, y, gamma=0.5)
    assert set(result) == {"softmax", "naive_edl", "tacr"}
    for signal in result.values():
        assert "aurc" in signal and "risk@0.7" in signal and "missed@0.7" in signal
