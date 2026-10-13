"""Evaluate and compare three conformal triage paradigms on real credit datasets:

1. Standard Conformal Prediction (SCP) with raw Softmax / 1 - P.
2. Evidential Conformal Prediction (ECP) with naive scalar uncertainty u.
3. Topology-Aware Conformal Auditor (TACR / RiskGNN++ V2) with inter-branch conflict penalty.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from riskgnn_pp.conformal_triage import TopologyAwareConformalAuditor


def evaluate_triage(
    cal_p: np.ndarray,
    cal_u: np.ndarray,
    cal_c: np.ndarray,
    cal_y: np.ndarray,
    test_p: np.ndarray,
    test_u: np.ndarray,
    test_c: np.ndarray,
    test_y: np.ndarray,
    epsilon: float = 0.05,
) -> dict:
    # 1. Softmax baseline: S = 1 - p (gamma=0, beta=0)
    auditor_softmax = TopologyAwareConformalAuditor(epsilon=epsilon, gamma=0.0, beta=0.0)
    auditor_softmax.calibrate(cal_p, cal_c, cal_y, cal_u)
    res_softmax = auditor_softmax.audit(test_p, test_c, test_y, test_u)

    # 2. Naive Evidential baseline: S = (1 - p) + beta * u (gamma=0, beta=0.2)
    auditor_edl = TopologyAwareConformalAuditor(epsilon=epsilon, gamma=0.0, beta=0.2)
    auditor_edl.calibrate(cal_p, cal_c, cal_y, cal_u)
    res_edl = auditor_edl.audit(test_p, test_c, test_y, test_u)

    # 3. RiskGNN++ V2 (TACR): S = (1 - p) + gamma * conflict + beta * u (gamma=0.6, beta=0.05)
    auditor_tacr = TopologyAwareConformalAuditor(epsilon=epsilon, gamma=0.6, beta=0.05)
    auditor_tacr.calibrate(cal_p, cal_c, cal_y, cal_u)
    res_tacr = auditor_tacr.audit(test_p, test_c, test_y, test_u)

    def _pack(r):
        return {
            "q_hat": float(r.conformal_threshold),
            "coverage": float(r.empirical_coverage),
            "deferral_rate": float(r.deferral_rate),
            "auto_rate": float(r.auto_decision_rate),
            "ood_rate": float(r.ood_rate),
            "high_conflict_deferral": float(r.high_conflict_deferral_rate),
            "low_conflict_deferral": float(r.low_conflict_deferral_rate),
        }

    return {
        "softmax_cp": _pack(res_softmax),
        "edl_cp": _pack(res_edl),
        "tacr_ours": _pack(res_tacr),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preds-file", type=Path, required=True)
    parser.add_argument("--arm", type=str, default="plus")
    parser.add_argument("--epsilon", type=float, default=0.05)
    args = parser.parse_args()

    data = np.load(args.preds_file)
    cal_p = data[f"{args.arm}_cal_p"]
    cal_u = data[f"{args.arm}_cal_uncertainty"]
    cal_c = data[f"{args.arm}_cal_conflict"]
    cal_y = data["cal_y"]

    test_p = data[f"{args.arm}_test_p"]
    test_u = data[f"{args.arm}_test_uncertainty"]
    test_c = data[f"{args.arm}_test_conflict"]
    test_y = data["test_y"]

    res = evaluate_triage(
        cal_p, cal_u, cal_c, cal_y, test_p, test_u, test_c, test_y, epsilon=args.epsilon
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
