"""Replay saved RiskGNN paper predictions without retraining or tuning parameters."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "paper_conformal", root / "models/riskgnnpp/riskgnn_pp/conformal_triage.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    rows = []
    input_hashes = {}
    for dataset in ("uk", "smesd"):
        run = root / f"models/runs/riskgnnpp-{dataset}-20261013"
        for seed in (14, 42, 2026):
            prediction_path = run / f"seed_{seed}/predictions.npz"
            input_hashes[str(prediction_path.relative_to(root))] = hashlib.sha256(
                prediction_path.read_bytes()
            ).hexdigest()
            data = np.load(prediction_path)
            y = data["test_y"]
            for arm in ("plus", "plusplus"):
                p, c, u = (data[f"{arm}_test_{key}"] for key in ("p", "conflict", "uncertainty"))
                error = (p[:, 1] >= 0.5) != y
                for name, gamma, beta in (
                    ("softmax_cp", 0, 0),
                    ("evidence_cp", 0, 0.2),
                    ("tacr_cp", 0.6, 0.05),
                ):
                    auditor = module.TopologyAwareConformalAuditor(
                        epsilon=0.05, gamma=gamma, beta=beta
                    )
                    auditor.calibrate(
                        data[f"{arm}_cal_p"],
                        data[f"{arm}_cal_conflict"],
                        data["cal_y"],
                        data[f"{arm}_cal_uncertainty"],
                    )
                    r = auditor.audit(p, c, y, u)
                    auto = np.array([len(s) == 1 for s in r.prediction_sets])
                    assert np.isclose(r.deferral_rate + r.auto_decision_rate + r.ood_rate, 1)
                    rows.append(
                        dict(
                            dataset=dataset,
                            seed=seed,
                            arm=arm,
                            method=name,
                            coverage=r.empirical_coverage,
                            auto_rate=r.auto_decision_rate,
                            ood_rate=r.ood_rate,
                            auto_error=float(error[auto].mean()) if auto.any() else None,
                        )
                    )
                for budget in (0.1, 0.2, 0.3, 0.4, 0.5):
                    scores = {
                        "uncertainty": u,
                        "margin": 0.5 - np.abs(p[:, 1] - 0.5),
                        "conflict_rank": 0.5 - np.abs(p[:, 1] - 0.5) + 0.6 * c,
                    }
                    for name, score in scores.items():
                        order = np.argsort(-score, kind="stable")
                        auto = order[int(np.ceil(len(y) * budget)) :]
                        rows.append(
                            dict(
                                dataset=dataset,
                                seed=seed,
                                arm=arm,
                                method=name,
                                budget=budget,
                                n_auto=len(auto),
                                auto_error=float(error[auto].mean()),
                            )
                        )
    summary = []
    keys = sorted(set((r["dataset"], r["arm"], r["method"], r.get("budget", -1)) for r in rows))
    for dataset, arm, method, budget in keys:
        group = [
            r
            for r in rows
            if (r["dataset"], r["arm"], r["method"], r.get("budget", -1))
            == (dataset, arm, method, budget)
        ]
        out = dict(dataset=dataset, arm=arm, method=method, budget=None if budget == -1 else budget)
        for key in ("coverage", "auto_rate", "ood_rate", "auto_error"):
            if key in group[0]:
                values = [r[key] for r in group]
                out[key] = dict(mean=float(np.mean(values)), std=float(np.std(values, ddof=1)))
        summary.append(out)
    args.output.write_text(
        json.dumps(
            dict(
                input_sha256=input_hashes,
                auditor_sha256=hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest(),
                protocol=dict(
                    seeds=[14, 42, 2026],
                    epsilon=0.05,
                    tacr_gamma=0.6,
                    tacr_beta=0.05,
                    budget_gamma=0.6,
                    prediction_threshold=0.5,
                    review_count="ceil(N * budget)",
                    tie_break="stable input order",
                    probability="raw primary softmax",
                ),
                summary=summary,
                rows=rows,
            ),
            indent=2,
        )
        + "\n"
    )
    print(f"Replayed {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
