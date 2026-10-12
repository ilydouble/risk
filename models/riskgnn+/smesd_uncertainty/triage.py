"""Replayable, label-blind selection comparisons for the paper's Table 3."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

REQUIRED = (
    "cal_ids",
    "test_ids",
    "cal_y",
    "test_y",
    "comrisk_cal_p",
    "comrisk_test_p",
    "plus_cal_p",
    "plus_test_p",
    "plus_cal_u",
    "plus_test_u",
)


def validate_predictions(data: dict[str, np.ndarray]) -> None:
    for key in REQUIRED:
        if key not in data:
            raise ValueError(f"Missing prediction field: {key}")
    for split in ("cal", "test"):
        labels = np.asarray(data[f"{split}_y"])
        ids = np.asarray(data[f"{split}_ids"])
        if labels.ndim != 1 or not len(labels) or not np.isin(labels, [0, 1]).all():
            raise ValueError(f"{split}: expected non-empty binary labels")
        if ids.shape != labels.shape or len(np.unique(ids)) != len(ids):
            raise ValueError(f"{split}: IDs must be unique and aligned with labels")
        for model in ("comrisk", "plus"):
            p = np.asarray(data[f"{model}_{split}_p"])
            if p.shape != (len(labels), 2) or not np.isfinite(p).all():
                raise ValueError(
                    f"{model}/{split}: invalid probability shape or values"
                )
            if (p < 0).any() or (p > 1).any() or not np.allclose(p.sum(1), 1):
                raise ValueError(f"{model}/{split}: probabilities must sum to one")
        u = np.asarray(data[f"plus_{split}_u"])
        if (
            u.shape != labels.shape
            or not np.isfinite(u).all()
            or ((u < 0) | (u > 1)).any()
        ):
            raise ValueError(f"{split}: invalid uncertainty")
    if np.intersect1d(data["cal_ids"], data["test_ids"]).size:
        raise ValueError("Calibration and test IDs overlap")


def decision_metrics(y: np.ndarray, pred: np.ndarray, auto: np.ndarray) -> dict:
    n = len(y)
    count = int(auto.sum())
    errors = int(((pred != y) & auto).sum())
    approved = auto & (pred == 0)
    rejected = auto & (pred == 1)
    return {
        "n": n,
        "auto_count": count,
        "auto_rate": count / n,
        "review_rate": 1 - count / n,
        "auto_errors": errors,
        "auto_accuracy": 1 - errors / count if count else None,
        "auto_risk": errors / count if count else None,
        "approve_count": int(approved.sum()),
        "reject_count": int(rejected.sum()),
        "approved_defaults": int((approved & (y == 1)).sum()),
        "rejected_nondefaults": int((rejected & (y == 0)).sum()),
        "approved_default_rate": float(y[approved].mean()) if approved.any() else None,
        "rejected_nondefault_rate": float((y[rejected] == 0).mean())
        if rejected.any()
        else None,
    }


def fixed_budget_mask(
    scores: np.ndarray, ids: np.ndarray, review_budget: float
) -> np.ndarray:
    """Select by score only; break ties by stable company ID, never by outcome."""
    if not 0 <= review_budget <= 1:
        raise ValueError("Review budget must lie in [0, 1]")
    order = np.lexsort((ids, -scores))
    auto = np.zeros(len(scores), dtype=bool)
    auto[order[: int(np.floor(len(scores) * (1 - review_budget) + 1e-9))]] = True
    return auto


def compare_triage(
    data: dict[str, np.ndarray],
    epsilon: float = 0.05,
    beta: float = 0.2,
    budgets: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9),
) -> list[dict]:
    from riskgnn_plus.conformal import ConformalRiskAuditor

    validate_predictions(data)
    if not np.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and non-negative")
    y = data["test_y"]
    rows = []
    for model, name, weight, kind in (
        ("comrisk", "ComRisk + CP", 0.0, "none"),
        ("plus", "RiskGNN+ + CP (beta=0)", 0.0, "none"),
        ("plus", "RiskGNN+ + entropy CP", beta, "entropy"),
        ("plus", "RiskGNN+ + evidence CP", beta, "evidence"),
    ):
        cp, tp = data[f"{model}_cal_p"], data[f"{model}_test_p"]
        cu, tu = np.zeros(len(cp)), np.zeros(len(tp))
        if kind == "evidence":
            cu, tu = data["plus_cal_u"], data["plus_test_u"]
        elif kind == "entropy":
            cu = -(cp * np.log(np.clip(cp, 1e-12, 1))).sum(1) / np.log(2)
            tu = -(tp * np.log(np.clip(tp, 1e-12, 1))).sum(1) / np.log(2)
        auditor = ConformalRiskAuditor(epsilon=epsilon, beta=weight)
        q = auditor.calibrate(cp, cu, data["cal_y"])
        result = auditor.audit(tp, tu, y)
        sizes = np.array([len(s) for s in result.prediction_sets])
        pred = np.array(
            [next(iter(s)) if len(s) == 1 else -1 for s in result.prediction_sets]
        )
        rows.append(
            {
                "protocol": "conformal",
                "method": name,
                "epsilon": epsilon,
                "beta": weight,
                "threshold": q if np.isfinite(q) else None,
                "threshold_is_infinite": not np.isfinite(q),
                "coverage": result.empirical_coverage,
                "ambiguous_rate": float((sizes == 2).mean()),
                "empty_rate": float((sizes == 0).mean()),
                **decision_metrics(y, pred, sizes == 1),
            }
        )
        if kind == "evidence":
            evidence_auto = sizes == 1
            evidence_pred = pred
    matched_budget = 1 - float(evidence_auto.mean())
    for model, name in (
        ("comrisk", "ComRisk confidence"),
        ("plus", "RiskGNN+ confidence"),
    ):
        p = data[f"{model}_test_p"]
        auto = fixed_budget_mask(p.max(1), data["test_ids"], matched_budget)
        rows.append(
            {
                "protocol": "matched_evidence_cp_coverage",
                "method": name,
                **decision_metrics(y, p.argmax(1), auto),
            }
        )
    rows.append(
        {
            "protocol": "matched_evidence_cp_coverage",
            "method": "RiskGNN+ + evidence CP",
            **decision_metrics(y, evidence_pred, evidence_auto),
        }
    )
    for model, kind, name in (
        ("comrisk", "confidence", "ComRisk confidence"),
        ("plus", "confidence", "RiskGNN+ confidence"),
        ("plus", "evidence", "RiskGNN+ evidence uncertainty"),
    ):
        cp, tp = data[f"{model}_cal_p"], data[f"{model}_test_p"]
        cs, ts = cp.max(1), tp.max(1)
        if kind == "evidence":
            cs, ts = -data["plus_cal_u"], -data["plus_test_u"]
        pred = tp.argmax(1)
        for budget in budgets:
            auto = fixed_budget_mask(ts, data["test_ids"], budget)
            rows.append(
                {
                    "protocol": "fixed_budget",
                    "method": name,
                    "review_budget": budget,
                    **decision_metrics(y, pred, auto),
                }
            )
            # Deployment threshold is chosen on calibration scores, without labels.
            k = int(np.floor(len(cs) * (1 - budget) + 1e-9))
            threshold = float(np.sort(cs)[-k]) if k else float("inf")
            rows.append(
                {
                    "protocol": "calibrated_threshold",
                    "method": name,
                    "review_budget": budget,
                    "threshold": threshold if np.isfinite(threshold) else None,
                    "threshold_is_infinite": not np.isfinite(threshold),
                    **decision_metrics(y, pred, ts >= threshold),
                }
            )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = row["protocol"], row["method"], row.get("review_budget")
        groups.setdefault(key, []).append(row)
    summary = []
    for (protocol, method, budget), group in groups.items():
        result = {
            "protocol": protocol,
            "method": method,
            "review_budget": budget,
            "seeds": len(group),
        }
        for metric in (
            "auto_rate",
            "auto_risk",
            "review_rate",
            "coverage",
            "empty_rate",
        ):
            values = [r[metric] for r in group if r.get(metric) is not None]
            if values:
                result[f"{metric}_mean"] = float(np.mean(values))
                result[f"{metric}_std"] = (
                    float(np.std(values, ddof=1)) if len(values) > 1 else None
                )
        summary.append(result)
    return summary


def write_report(rows: list[dict], output: Path, metadata: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    paired = []
    for row in rows:
        if row["protocol"] != "fixed_budget" or row["method"] == "ComRisk confidence":
            continue
        baseline = next(
            r
            for r in rows
            if r["protocol"] == "fixed_budget"
            and r["method"] == "ComRisk confidence"
            and r.get("seed") == row.get("seed")
            and r["review_budget"] == row["review_budget"]
        )
        paired.append(
            {
                "seed": row.get("seed"),
                "method": row["method"],
                "review_budget": row["review_budget"],
                "auto_risk_delta_vs_comrisk": (
                    row["auto_risk"] - baseline["auto_risk"]
                    if row["auto_risk"] is not None
                    and baseline["auto_risk"] is not None
                    else None
                ),
            }
        )
    report = {
        "metadata": metadata,
        "rows": rows,
        "summary": summarize(rows),
        "paired_fixed_budget_differences": paired,
    }
    (output / "triage_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (output / "triage_results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.2)
    args = parser.parse_args()
    rows, sources, seeds = [], [], set()
    reference = None
    for path in args.predictions:
        with np.load(path, allow_pickle=False) as archive:
            data = dict(archive)
        identity = {
            key: data[key] for key in ("cal_ids", "test_ids", "cal_y", "test_y")
        }
        if reference is not None and any(
            not np.array_equal(identity[key], reference[key]) for key in identity
        ):
            raise ValueError(
                "Cannot aggregate predictions with different splits or labels"
            )
        reference = identity
        seed = int(data["seed"])
        if seed in seeds:
            raise ValueError(f"Duplicate seed: {seed}")
        seeds.add(seed)
        rows.extend(
            dict(row, seed=seed)
            for row in compare_triage(data, args.epsilon, args.beta)
        )
        sources.append(
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    write_report(
        rows,
        args.output,
        {
            "prediction_sources": sources,
            "epsilon": args.epsilon,
            "beta": args.beta,
            "test_labels_used_for_selection": False,
            "evaluation_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        },
    )


if __name__ == "__main__":
    main()
