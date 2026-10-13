"""Aggregate benchmark runs: recalibrated metrics, risk--coverage triage, paired tests.

Reads one or more benchmark output directories (each containing ``seed_*/``
with ``predictions.npz``), merges seeds across directories, and reports:

1. Raw metrics per arm (ROC-AUC, PR-AUC, ECE, Brier, accuracy).
2. The same metrics after isotonic recalibration on the calibration split.
3. Risk--coverage triage (AURC and selective risk) for ambiguity, uncertainty,
   and conflict-guided ranking (legacy output key ``tacr``).
4. Paired significance tests across seeds, distinguishing raw from recalibrated AP.

Usage::

    python analyze_runs.py \
        --run-dir ../../models/runs/riskgnnpp-uk-20261013 \
        --run-dir ../../models/runs/riskgnnpp-uk-20261013-ext \
        --dataset uk --output ../../models/runs/analysis-uk-20261013
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from riskgnn_plus.evaluator import evaluate_risk_predictions
from riskgnn_pp.triage_analysis import (
    DEFAULT_COVERAGES,
    Recalibrator,
    evaluate_triage,
    tune_gamma,
)

TRIAGE_ARMS = ("plus", "plusplus", "plusplus_nodiscount", "plusplus_noreg")
DEFAULT_ARMS = ("comrisk", "riskgnn", "plus", "plusplus")
RECAL_METHOD = {"uk": "isotonic", "smesd": "platt"}
# Headline paired comparisons: (metric_key, method_a, method_b, human_readable)
PAIRED_SPECS = (
    ("prAuc", "plusplus", "plus", "Recalibrated AP: RiskGNN++ vs RiskGNN+"),
    ("rocAuc", "plusplus", "plus", "ROC-AUC: RiskGNN++ vs RiskGNN+"),
    ("ece", "plusplus", "plus", "ECE: RiskGNN++ vs RiskGNN+"),
    ("brier", "plusplus", "plus", "Brier: RiskGNN++ vs RiskGNN+"),
    ("prAuc", "plusplus", "comrisk", "Recalibrated AP: RiskGNN++ vs ComRisk"),
    (
        "aurc",
        "plusplus:tacr",
        "plusplus:softmax",
        "AURC: conflict ranking vs ambiguity",
    ),
    (
        "aurc",
        "plusplus:tacr",
        "plusplus:naive_edl",
        "AURC: conflict ranking vs uncertainty",
    ),
    (
        "risk@0.7",
        "plusplus:tacr",
        "plusplus:softmax",
        "Risk@0.7: conflict ranking vs ambiguity",
    ),
    (
        "risk@0.7",
        "plusplus:tacr",
        "plusplus:naive_edl",
        "Risk@0.7: conflict ranking vs uncertainty",
    ),
)
RAW_PAIRED_SPECS = (
    ("plusplus", "plus", "Raw AP: RiskGNN++ vs RiskGNN+"),
    ("plusplus", "comrisk", "Raw AP: RiskGNN++ vs ComRisk"),
)


def discover_seeds(run_dirs: list[Path]) -> dict[int, Path]:
    seeds: dict[int, Path] = {}
    for run_dir in run_dirs:
        for seed_dir in sorted(run_dir.glob("seed_*")):
            if not (seed_dir / "predictions.npz").is_file():
                continue
            seed = int(seed_dir.name.split("_")[1])
            seeds[seed] = seed_dir
    if not seeds:
        raise FileNotFoundError("no seed_*/predictions.npz found in the given run dirs")
    return dict(sorted(seeds.items()))


def _per_seed_metrics(
    dataset: str, seed: int, seed_dir: Path, arms: tuple[str, ...]
) -> dict:
    data = np.load(seed_dir / "predictions.npz")
    cal_y = data["cal_y"]
    test_y = data["test_y"]
    method = RECAL_METHOD.get(dataset, "isotonic")
    row: dict = {"seed": seed, "raw": {}, "recalibrated": {}, "triage": {}, "gamma": {}}
    for arm in arms:
        key = f"{arm}_test_p"
        if key not in data:
            continue
        raw_p = data[key][:, 1]
        cal_p = data[f"{arm}_cal_p"][:, 1]
        row["raw"][arm] = evaluate_risk_predictions(raw_p, test_y)

        recal = Recalibrator(method=method).fit(cal_p, cal_y)
        test_p = recal.transform(raw_p)
        row["recalibrated"][arm] = evaluate_risk_predictions(test_p, test_y)

        if arm in TRIAGE_ARMS:
            cal_conflict = data[f"{arm}_cal_conflict"]
            test_conflict = data[f"{arm}_test_conflict"]
            test_u = data[f"{arm}_test_uncertainty"]
            gamma = tune_gamma(recal.transform(cal_p), cal_conflict, cal_y)
            row["gamma"][arm] = gamma
            row["triage"][arm] = evaluate_triage(
                test_p, test_u, test_conflict, test_y, gamma=gamma
            )
    return row


def _bootstrap_ci(
    diff: np.ndarray, iterations: int = 10000, seed: int = 0
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(diff)
    draws = rng.choice(diff, size=(iterations, n), replace=True).mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def paired_stats(
    a: np.ndarray, b: np.ndarray, *, lower_is_better: bool = False
) -> dict:
    from scipy.stats import ttest_rel, wilcoxon

    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    diff = a - b
    n = len(diff)
    if n < 2:
        return {"n": n, "mean_diff": float(diff.mean()) if n else 0.0}
    ci_low, ci_high = _bootstrap_ci(diff)
    t_p = float(ttest_rel(a, b).pvalue)
    if np.allclose(diff, 0.0):
        w_p = 1.0
    else:
        w_p = float(wilcoxon(a, b).pvalue)
    return {
        "n": n,
        "mean_a": float(a.mean()),
        "mean_b": float(b.mean()),
        "mean_diff": float(diff.mean()),
        "std_diff": float(diff.std(ddof=1)),
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "t_p": t_p,
        "wilcoxon_p": w_p,
        "wins": int(((diff < 0) if lower_is_better else (diff > 0)).sum()),
    }


def _metric_series(
    rows: list[dict], arm: str, metric: str, calibrated: bool
) -> np.ndarray:
    store = "recalibrated" if calibrated else "raw"
    return np.asarray([row[store][arm][metric] for row in rows], dtype=np.float64)


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
    }


def _write_markdown(report: dict, path: Path) -> None:
    lines = [f"# Analysis: {report['dataset']} ({len(report['seeds'])} seeds)", ""]
    lines.append(f"Seeds: {report['seeds']}")
    lines.append(
        f"Recalibration: `{report['recalibration']}` on the calibration split."
    )
    lines.append("")

    lines += ["## Raw vs recalibrated metrics", ""]
    for arm in report["arms"]:
        lines.append(f"### {arm}")
        lines.append("")
        lines.append("| Metric | Raw | Recalibrated |")
        lines.append("| --- | --- | --- |")
        for metric in ("rocAuc", "prAuc", "ece", "brier", "accuracy"):
            raw = report["raw"][arm][metric]
            rec = report["recalibrated"][arm][metric]
            lines.append(
                f"| {metric} | {raw['mean']:.4f} ± {raw['std']:.4f} | "
                f"{rec['mean']:.4f} ± {rec['std']:.4f} |"
            )
        lines.append("")

    lines += ["## Triage (risk--coverage, recalibrated)", ""]
    for arm in report["arms"]:
        if arm not in report["triage"]:
            continue
        lines.append(f"### {arm} (gamma per seed: {report['gamma'][arm]})")
        lines.append("")
        header = " | ".join(f"Risk@{c:.1f} ↓" for c in DEFAULT_COVERAGES)
        lines.append(f"| Signal | AURC ↓ | {header} |")
        lines.append(
            "| --- | --- | " + " | ".join("---" for _ in DEFAULT_COVERAGES) + " |"
        )
        for signal in ("softmax", "naive_edl", "tacr"):
            stats = report["triage"][arm][signal]
            cells = " | ".join(
                f"{stats[f'risk@{c:.1f}']['mean']:.4f}" for c in DEFAULT_COVERAGES
            )
            lines.append(f"| {signal} | {stats['aurc']['mean']:.4f} | {cells} |")
        lines.append("")

    lines += ["## Paired significance across seeds", ""]
    lines.append("| Comparison | mean diff | 95% CI | paired t p | Wilcoxon p | wins |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for entry in report["paired"]:
        lines.append(
            f"| {entry['label']} | {entry['mean_diff']:+.4f} | "
            f"[{entry['ci95_low']:+.4f}, {entry['ci95_high']:+.4f}] | "
            f"{entry['t_p']:.4f} | {entry['wilcoxon_p']:.4f} | "
            f"{entry['wins']}/{entry['n']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--dataset", choices=("uk", "smesd"), required=True)
    parser.add_argument("--arms", nargs="+", default=list(DEFAULT_ARMS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    seeds = discover_seeds(args.run_dir)
    arms = tuple(
        a
        for a in args.arms
        if any(f"{a}_test_p" in np.load(d / "predictions.npz") for d in seeds.values())
    )
    rows = [_per_seed_metrics(args.dataset, seed, d, arms) for seed, d in seeds.items()]

    report: dict = {
        "dataset": args.dataset,
        "seeds": list(seeds),
        "arms": list(arms),
        "recalibration": RECAL_METHOD.get(args.dataset, "isotonic"),
        "run_dirs": [str(p) for p in args.run_dir],
        "raw": {
            arm: {
                m: _summary(_metric_series(rows, arm, m, calibrated=False))
                for m in ("rocAuc", "prAuc", "ece", "brier", "accuracy")
            }
            for arm in arms
        },
        "recalibrated": {
            arm: {
                m: _summary(_metric_series(rows, arm, m, calibrated=True))
                for m in ("rocAuc", "prAuc", "ece", "brier", "accuracy")
            }
            for arm in arms
        },
        "triage": {},
        "gamma": {},
        "paired": [],
    }
    for arm in arms:
        if arm not in rows[0]["triage"]:
            continue
        report["gamma"][arm] = [row["gamma"][arm] for row in rows]
        report["triage"][arm] = {
            signal: {
                metric: _summary(
                    np.asarray([row["triage"][arm][signal][metric] for row in rows])
                )
                for metric in rows[0]["triage"][arm][signal]
            }
            for signal in ("softmax", "naive_edl", "tacr")
        }

    for metric, a_key, b_key, label in PAIRED_SPECS:
        a_arm, b_arm = a_key.split(":")[0], b_key.split(":")[0]
        if a_arm not in arms or b_arm not in arms:
            continue
        a_series = np.asarray([_series_for(row, a_key, metric) for row in rows])
        b_series = np.asarray([_series_for(row, b_key, metric) for row in rows])
        stats = paired_stats(
            a_series,
            b_series,
            lower_is_better=metric in {"ece", "brier", "aurc", "risk@0.7"},
        )
        stats["label"] = label
        stats["metric"] = metric
        report["paired"].append(stats)

    for a_arm, b_arm, label in RAW_PAIRED_SPECS:
        if a_arm not in arms or b_arm not in arms:
            continue
        stats = paired_stats(
            _metric_series(rows, a_arm, "prAuc", calibrated=False),
            _metric_series(rows, b_arm, "prAuc", calibrated=False),
        )
        stats["label"] = label
        stats["metric"] = "raw_prAuc"
        report["paired"].append(stats)

    (args.output / "analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_markdown(report, args.output / "analysis.md")
    print(json.dumps(report["paired"], ensure_ascii=False, indent=2))


def _series_for(row: dict, key: str, metric: str) -> float:
    if ":" in key:
        arm, tail = key.split(":")
        if tail in ("softmax", "naive_edl", "tacr"):
            return row["triage"][arm][tail][metric]
        if tail in row["triage"][arm]["tacr"]:
            return row["triage"][arm]["tacr"][tail]
        return row["recalibrated"][arm][tail]
    return row["recalibrated"][key][metric]


if __name__ == "__main__":
    main()
