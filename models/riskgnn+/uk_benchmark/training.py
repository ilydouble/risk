"""Train and compare ComRisk, RiskGNN and RiskGNN+ on the UK benchmark.

Mirrors ``run_smesd_experiments.py``'s three-arm design but trains the real
dual-branch evidential RiskGNN+ instead of a plain classifier with entropy passed
off as uncertainty:

* ``comrisk`` -- frozen-compatible RiskGNN base, no community prior, classifier head.
* ``riskgnn`` -- same base plus the Bayesian-smoothed community (SIC section) prior.
* ``plus``    -- ``RiskGNNPlus``: node/graph evidential heads, DST fusion and the
  discriminative primary classifier, trained with ``EvidentialRiskLoss``.

All three share the input tensors, embedding initialisation, class weighting,
optimiser schedule, seed, early-stopping rule and epoch budget, so differences are
architectural. Reported metrics are ROC-AUC, PR-AUC, ECE and Brier on the held-out
test snapshot, with the inter-branch conflict strata and the conformal audit for
RiskGNN+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from riskgnn_plus import (
    AuditDecision,
    ConformalRiskAuditor,
    EvidentialRiskLoss,
    RiskGNNPlus,
    analyze_conflict_contagion,
    evaluate_risk_predictions,
)
from sklearn.metrics import roc_auc_score
from smesd_uncertainty.comrisk_base.gnn import RiskGNN
from smesd_uncertainty.comrisk_base.utils import (
    Classifier,
    build_group_prior_feature,
    build_group_prior_feature_loo,
    build_incidence,
    fit_bayesian_group_prior,
)
from torch import optim

from uk_benchmark.data import SPLIT_ORDER, load_uk_benchmark, summarize

ARMS = ("comrisk", "riskgnn", "plus")
ARMS_WITH_PRIOR = {"riskgnn", "plus"}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def build_incidences(dataset: dict) -> dict:
    """Turn the loader's per-kind group maps into HyperGNN incidence tuples."""
    return {
        name: [
            build_incidence(dataset["company_num"], groups)
            for groups in dataset["hypergraphs"][name]
        ]
        for name in SPLIT_ORDER
    }


def _community_groups(communities: list[str], idx: np.ndarray) -> dict:
    groups: dict[str, list[int]] = {}
    for community, global_idx in zip(communities, idx, strict=True):
        groups.setdefault(community, []).append(int(global_idx))
    return groups


def build_priors(dataset: dict) -> dict:
    """Bayesian community prior over SIC sections, fit on the training labels only.

    Training rows use the leave-one-out feature (a singleton group carries no
    information about its only member); validation/calibration/test rows use the
    fitted group prior with an unseen-group fallback to the global rate.
    """
    train = dataset["splits"]["train"]
    train_groups = _community_groups(train["community"], train["idx"])
    prior, alpha, beta, global_mean, stats = fit_bayesian_group_prior(
        train_groups, train["y"], train["idx"]
    )
    priors = {
        "train": build_group_prior_feature_loo(
            train_groups, train["idx"], train["y"], stats, alpha, beta, global_mean
        )
    }
    for name in ("valid", "cal", "test"):
        split = dataset["splits"][name]
        groups = _community_groups(split["community"], split["idx"])
        priors[name] = build_group_prior_feature(groups, split["idx"], prior, global_mean)
    return priors


def class_weights_for(dataset: dict, mode: str):
    if mode == "uniform":
        return None
    train_y = np.asarray(dataset["splits"]["train"]["y"], dtype=np.int64)
    positives = int(train_y.sum())
    negatives = int(len(train_y) - positives)
    if positives == 0:
        raise ValueError("training split has no positive labels")
    return (1.0, negatives / positives)


def model_config(dataset: dict, arm: str, device: torch.device) -> dict:
    return {
        "input_dim": 16,
        "output_dim": 12,
        "company_num": dataset["company_num"],
        "person_num": 0,
        "rel_num": len(dataset["relation_names"]),
        "cause_type_num": 1,
        "court_type_num": 1,
        "category_num": 1,
        "time_label_num": 1,
        "device": device,
        "com_initial_emb": dataset["com_emb"],
        "person_initial_emb": dataset["per_emb"],
        "n_company_attr_dims": len(dataset["feature_names"]),
        "dropout": 0.2,
        "use_hypergraph": True,
        "use_edgegraph": True,
        "hyper_impl": "vectorized",
        # SAME_ADDRESS weights are non-uniform while the other three relations are
        # exactly 1.0, so the base layer must be told up front that every relation
        # uses the weight-only path (see the message() comment in comrisk_base/gnn.py).
        "hete_scalar_weights": True,
        "use_community_prior": arm in ARMS_WITH_PRIOR,
    }


def make_arm(dataset: dict, arm: str, device: torch.device) -> nn.Module:
    config = model_config(dataset, arm, device)
    if arm == "plus":
        return RiskGNNPlus(**config).to(device)
    return nn.Sequential(RiskGNN(**config), Classifier(12, 2)).to(device)


def forward_arm(model: nn.Module, arm: str, split: dict, hyper, prior):
    if arm == "plus":
        return model(split["risk"], split["attr"], split["graph"], hyper, split["idx"], prior)
    emb = model[0](split["risk"], split["attr"], split["graph"], hyper, split["idx"], prior)
    return model[1](emb)


def arm_probabilities(arm: str, output) -> torch.Tensor:
    return output.probabilities if arm == "plus" else output.exp()


def fit_arm(
    dataset: dict,
    arms_config: dict,
    arm: str,
    seed: int,
    epochs: int,
    lr: float,
    device: torch.device,
    class_weights,
    eval_every: int,
    output_dir: Path,
) -> tuple[dict, dict]:
    seed_everything(seed)
    model = make_arm(dataset, arm, device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    loss_fn = EvidentialRiskLoss(class_weights=class_weights) if arm == "plus" else None
    weight_tensor = (
        torch.tensor(class_weights, dtype=torch.float32, device=device)
        if class_weights is not None
        else None
    )

    splits = dataset["splits"]
    hypergraphs = arms_config["incidences"]
    priors = arms_config["priors"]
    prior_for = priors if arm in ARMS_WITH_PRIOR else {name: None for name in SPLIT_ORDER}

    def run(split_name: str):
        return forward_arm(
            model,
            arm,
            splits[split_name],
            hypergraphs[split_name],
            prior_for[split_name],
        )

    train_y = torch.as_tensor(splits["train"]["y"], dtype=torch.long, device=device)
    valid_auc = -1.0
    best_state, best_epoch = None, 0
    started = time.monotonic()
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        result = run("train")
        if arm == "plus":
            loss = loss_fn(
                result.fused_alpha,
                result.node_alpha,
                result.graph_alpha,
                train_y,
                primary_logits=result.primary_logits,
            )["loss"]
        else:
            loss = F.nll_loss(result, train_y, weight=weight_tensor)
        if not torch.isfinite(loss):
            raise RuntimeError(f"non-finite loss for {arm} at epoch {epoch}")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 0.25)
        optimizer.step()
        scheduler.step()

        if epoch % eval_every == 0 or epoch == epochs:
            model.eval()
            with torch.no_grad():
                probs = arm_probabilities(arm, run("valid"))
                auc = float(roc_auc_score(splits["valid"]["y"], probs[:, 1].cpu().numpy()))
            if auc > valid_auc:
                valid_auc, best_epoch = auc, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError(f"{arm} produced no finite validation epoch")
    model.load_state_dict(best_state)
    torch.save(best_state, output_dir / f"{arm}_checkpoint.pt")

    predictions: dict[str, np.ndarray] = {}
    metrics: dict[str, dict] = {}
    diagnostics: dict[str, np.ndarray] = {}
    model.eval()
    with torch.no_grad():
        for split_name in ("cal", "test"):
            result = run(split_name)
            probs = arm_probabilities(arm, result)
            predictions[f"{arm}_{split_name}_p"] = probs.cpu().numpy()
            metrics[split_name] = evaluate_risk_predictions(
                probs[:, 1].cpu().numpy(), splits[split_name]["y"]
            )
            if arm == "plus":
                diagnostics[f"plus_{split_name}_u"] = result.fused_uncertainty.cpu().numpy()
                diagnostics[f"plus_{split_name}_conflict"] = result.conflict.cpu().numpy()
                diagnostics[f"plus_{split_name}_node_p"] = (
                    result.node_probabilities.cpu().numpy()
                )
                diagnostics[f"plus_{split_name}_graph_p"] = (
                    result.graph_probabilities.cpu().numpy()
                )
    predictions.update(diagnostics)
    info = {
        "best_valid_auc": valid_auc,
        "best_epoch": best_epoch,
        "seconds": time.monotonic() - started,
        "cal": metrics["cal"],
        "test": metrics["test"],
    }
    return predictions, info


def _aggregate(rows: list[dict]) -> dict:
    summary: dict[str, dict[str, float]] = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        for metric in ("rocAuc", "prAuc", "ece", "brier"):
            values = np.asarray([row[metric] for row in arm_rows], dtype=np.float64)
            summary.setdefault(arm, {})[metric] = {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            }
    return summary


def _write_markdown(summary: dict, path: Path) -> None:
    lines = [
        "# UK 数据集 ComRisk / RiskGNN / RiskGNN+ 对照结果",
        "",
        "各训练种子测试集指标，均值 ± 样本标准差。",
        "正样本率约 3.6%，与 SMEsD 的 57.6% 不可直接比较绝对 AUC。",
        "",
        "| 模型 | ROC-AUC | PR-AUC | ECE | Brier |",
        "| --- | --- | --- | --- | --- |",
    ]
    label = {"comrisk": "ComRisk", "riskgnn": "RiskGNN (+community prior)", "plus": "RiskGNN+"}
    for arm in ARMS:
        stats = summary[arm]
        lines.append(
            f"| {label[arm]} | "
            f"{stats['rocAuc']['mean']:.4f} ± {stats['rocAuc']['std']:.4f} | "
            f"{stats['prAuc']['mean']:.4f} ± {stats['prAuc']['std']:.4f} | "
            f"{stats['ece']['mean']:.4f} ± {stats['ece']['std']:.4f} | "
            f"{stats['brier']['mean']:.4f} ± {stats['brier']['std']:.4f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("datasets/uk_dataset_v1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[14, 42, 2026])
    parser.add_argument("--epochs", type=int, default=250)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--eval-every", type=int, default=5)
    parser.add_argument("--class-weight", choices=["auto", "uniform"], default="auto")
    parser.add_argument("--edge-weights", choices=["dataset", "uniform"], default="dataset")
    parser.add_argument("--embed-seed", type=int, default=0)
    parser.add_argument("--max-nodes", type=int, default=None)
    parser.add_argument("--calib-fraction", type=float, default=0.5)
    parser.add_argument("--calib-seed", type=int, default=42)
    parser.add_argument("--no-standardize", action="store_true")
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.2)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    if args.epochs < 1 or args.eval_every < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("epochs/eval-every must be positive and seeds unique")
    if not 0 < args.epsilon < 1 or not np.isfinite(args.beta) or args.beta < 0:
        parser.error("Require epsilon in (0, 1) and finite beta >= 0")
    if args.output.exists():
        parser.error("Output already exists; use a new directory to preserve prior runs")

    args.output.mkdir(parents=True)
    torch.set_num_threads(args.threads)
    device = torch.device("cpu")

    dataset = load_uk_benchmark(
        args.data_dir,
        embed_seed=args.embed_seed,
        standardize=not args.no_standardize,
        calib_fraction=args.calib_fraction,
        calib_seed=args.calib_seed,
        max_nodes=args.max_nodes,
        uniform_weights=args.edge_weights == "uniform",
    )
    arms_config = {
        "incidences": build_incidences(dataset),
        "priors": build_priors(dataset),
    }
    class_weights = class_weights_for(dataset, args.class_weight)
    data_summary = summarize(dataset)
    print(json.dumps(data_summary, ensure_ascii=False, indent=2), flush=True)
    print(f"class_weights={class_weights}", flush=True)

    manifest = {
        "data_dir": str(args.data_dir.resolve()),
        "data": data_summary,
        "data_sha256": dataset["source_sha256"],
        "class_weights": list(class_weights) if class_weights else None,
        "edge_weights": args.edge_weights,
        "community_prior_group": "community (SIC section)",
        "arms": {
            "comrisk": "RiskGNN base, no community prior, classifier head",
            "riskgnn": "RiskGNN base + Bayesian community prior, classifier head",
            "plus": "RiskGNNPlus evidential dual-branch + DST fusion (real implementation)",
        },
        "protocol": {
            "epochs": args.epochs,
            "lr": args.lr,
            "eval_every": args.eval_every,
            "grad_clip": 0.25,
            "scheduler": "cosine",
            "select": "best validation ROC-AUC",
            "embedding": "frozen RandomState(embed_seed).normal(0, 0.1)",
            "preprocessing": "log1p counts + train-fit median impute and z-score",
        },
        "seeds": args.seeds,
        "epsilon": args.epsilon,
        "beta": args.beta,
        "torch": torch.__version__,
        "numpy": np.__version__,
        "device": "cpu",
        "source_sha256": {
            str(path.relative_to(Path(__file__).parents[1])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(
                path
                for folder in ("riskgnn_plus", "smesd_uncertainty", "uk_benchmark")
                for path in (Path(__file__).parents[1] / folder).rglob("*.py")
            )
        },
    }
    try:
        manifest["git_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001 - manifest must not fail the run
        manifest["git_head"] = "unknown"
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for relative in manifest["source_sha256"]:
        target = args.output / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).parents[1] / relative, target)

    rows: list[dict] = []
    audits: list[dict] = []
    for seed in args.seeds:
        seed_dir = args.output / f"seed_{seed}"
        seed_dir.mkdir()
        payload = {
            "seed": np.asarray(seed),
            "cal_y": dataset["splits"]["cal"]["y"],
            "test_y": dataset["splits"]["test"]["y"],
        }
        training: dict[str, dict] = {}
        plus_test_conflict = None
        plus_cal_p = plus_cal_u = plus_test_p = plus_test_u = None
        for arm in ARMS:
            print(f"[seed={seed}] training {arm}...", flush=True)
            predictions, info = fit_arm(
                dataset,
                arms_config,
                arm,
                seed,
                args.epochs,
                args.lr,
                device,
                class_weights,
                args.eval_every,
                seed_dir,
            )
            payload.update(predictions)
            training[arm] = info
            for split_name in ("test", "cal"):
                row = dict(info[split_name], arm=arm, seed=seed, split=split_name)
                if split_name == "test":
                    rows.append(row)
            if arm == "plus":
                plus_cal_p = predictions["plus_cal_p"]
                plus_cal_u = predictions["plus_cal_u"]
                plus_test_p = predictions["plus_test_p"]
                plus_test_u = predictions["plus_test_u"]
                plus_test_conflict = predictions["plus_test_conflict"]
        np.savez_compressed(seed_dir / "predictions.npz", **payload)
        (seed_dir / "training.json").write_text(
            json.dumps(training, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        test_y = dataset["splits"]["test"]["y"]
        cal_y = dataset["splits"]["cal"]["y"]
        strata = analyze_conflict_contagion(plus_test_conflict, test_y, quantiles=3)
        print(f"[seed={seed}] conflict strata:", flush=True)
        for row in strata:
            print(json.dumps(row, ensure_ascii=False), flush=True)
        auditor = ConformalRiskAuditor(epsilon=args.epsilon, beta=args.beta)
        q_hat = auditor.calibrate(plus_cal_p, plus_cal_u, cal_y)
        audit = auditor.audit(plus_test_p, plus_test_u, test_y)
        auto = int(
            sum(
                decision in (AuditDecision.AUTO_APPROVE, AuditDecision.AUTO_REJECT)
                for decision in audit.decisions
            )
        )
        audits.append(
            {
                "seed": seed,
                "q_hat": q_hat,
                "coverage": audit.empirical_coverage,
                "auto": auto,
                "deferral_rate": audit.deferral_rate,
                "ood_rate": audit.ood_rate,
                "conflict_strata": strata,
            }
        )
        print(
            f"[seed={seed}] conformal q_hat={q_hat:.4f} "
            f"coverage={audit.empirical_coverage:.4f} auto={auto} "
            f"deferral={audit.deferral_rate:.4f}",
            flush=True,
        )

    summary = _aggregate([row for row in rows if row["split"] == "test"])
    (args.output / "summary.json").write_text(
        json.dumps({"test": summary, "rows": rows, "audits": audits}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    _write_markdown(summary, args.output / "results.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    (args.output / "COMPLETE").write_text("All requested seeds completed.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
