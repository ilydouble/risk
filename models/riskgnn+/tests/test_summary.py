from __future__ import annotations

from smesd_uncertainty import summary


def result(variant: str, seed: int, auc: float, brier: float) -> dict:
    return {
        "scenario": {"noiseRatio": 0.4, "simulationSeed": seed},
        "seed": seed,
        "epochs": 500,
        "variant": variant,
        "test": {"rocAuc": auc, "prAuc": auc - 0.1, "brier": brier, "f1": auc - 0.2},
    }


def test_paired_summary_uses_matching_seeds_and_brier_direction() -> None:
    results = [
        result("comrisk_noisy", 14, 0.70, 0.22),
        result("riskgnn_gated", 14, 0.74, 0.19),
        result("comrisk_noisy", 42, 0.72, 0.21),
        result("riskgnn_gated", 42, 0.75, 0.20),
    ]

    comparisons = summary.summarize_comparisons(results, bootstrap_samples=100)
    paired = next(
        row
        for row in comparisons
        if row["target"] == "riskgnn_gated" and row["reference"] == "comrisk_noisy"
    )

    assert paired["pairedSeeds"] == [14, 42]
    assert abs(paired["testDelta"]["rocAuc"]["mean"] - 0.035) < 1e-12
    assert abs(paired["testDelta"]["brier"]["mean"] + 0.02) < 1e-12
    assert abs(paired["testDelta"]["brier"]["favorableMean"] - 0.02) < 1e-12
