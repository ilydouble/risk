"""Shared four-arm benchmark: ComRisk, RiskGNN, RiskGNN+, RiskGNN++.

All arms share the input tensors, embedding initialisation, class weighting,
optimiser schedule, seed and early-stopping rule, so differences are architectural.
RiskGNN++ additionally reports the diagnostics that support its mechanism claim:
per-node degree, contagion conflict (node vs neighbourhood) and mutual conflict
(neighbour vs neighbour), which are contrasted against the label-level topology
heterophily of the node.
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
from riskgnn_pp import RiskGNNPlusPlus
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
from uk_benchmark.data import load_uk_benchmark

SPLIT_ORDER = ("train", "valid", "cal", "test")

# arm name -> (model kind, RiskGNNPlusPlus ablation switches)
ARM_DEFS: dict[str, dict] = {
    "comrisk": {"kind": "backbone", "use_prior": False},
    "riskgnn": {"kind": "backbone", "use_prior": True},
    "plus": {"kind": "plus", "use_prior": True},
    "plusplus": {
        "kind": "plusplus",
        "use_prior": True,
        "use_topology_discount": True,
        "use_degree_likelihood": True,
    },
    "plusplus_nodiscount": {
        "kind": "plusplus",
        "use_prior": True,
        "use_topology_discount": False,
        "use_degree_likelihood": True,
    },
    "plusplus_noreg": {
        "kind": "plusplus",
        "use_prior": True,
        "use_topology_discount": True,
        "use_degree_likelihood": False,
    },
}
DEFAULT_ARMS = ("comrisk", "riskgnn", "plus", "plusplus")
EVIDENTIAL_ARMS = {"plus", "plusplus", "plusplus_nodiscount", "plusplus_noreg"}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def load_dataset(name: str, data_dir: Path, **kwargs) -> dict:
    if name == "uk":
        return load_uk_benchmark(data_dir, **kwargs)
    if name == "smesd":
        from smesd_benchmark.data import load_smesd_benchmark

        allowed = {"calib_fraction", "calib_seed"}
        return load_smesd_benchmark(
            data_dir, **{key: value for key, value in kwargs.items() if key in allowed}
        )
    raise ValueError(f"unknown dataset: {name}")


def build_incidences(dataset: dict) -> dict:
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
    """Bayesian community (SMEsD area / UK SIC section) prior fit on train labels only."""
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


def model_config(dataset: dict, arm: str, device: torch.device, plusplus_kwargs: dict) -> dict:
    definition = ARM_DEFS[arm]
    config = {
        "input_dim": 16,
        "output_dim": 12,
        "company_num": dataset["company_num"],
        "person_num": dataset["person_num"],
        "rel_num": len(dataset["relation_names"]),
        "cause_type_num": dataset.get("cause_type_num", 1),
        "court_type_num": dataset.get("court_type_num", 1),
        "category_num": dataset.get("category_num", 1),
        "time_label_num": dataset.get("time_label_num", 1),
        "device": device,
        "com_initial_emb": dataset["com_emb"],
        "person_initial_emb": dataset["per_emb"],
        "n_company_attr_dims": len(dataset["feature_names"]),
        "dropout": 0.2,
        "use_hypergraph": True,
        "use_edgegraph": True,
        "hyper_impl": "vectorized",
        # SMEsD keeps the original index convention (None); UK forces the
        # weight-only path because SAME_ADDRESS weights are non-uniform.
        "hete_scalar_weights": dataset.get("hete_scalar_weights", True),
        "use_community_prior": definition["use_prior"],
    }
    if definition["kind"] == "plusplus":
        config.update(plusplus_kwargs)
        config.update(
            use_topology_discount=definition["use_topology_discount"],
            use_degree_likelihood=definition["use_degree_likelihood"],
        )
    return config


def make_arm(dataset: dict, arm: str, device: torch.device, plusplus_kwargs: dict) -> nn.Module:
    config = model_config(dataset, arm, device, plusplus_kwargs)
    kind = ARM_DEFS[arm]["kind"]
    if kind == "plusplus":
        return RiskGNNPlusPlus(**config).to(device)
    if kind == "plus":
        return RiskGNNPlus(**config).to(device)
    return nn.Sequential(RiskGNN(**config), Classifier(12, 2)).to(device)


def forward_arm(model: nn.Module, arm: str, split: dict, hyper, prior):
    if ARM_DEFS[arm]["kind"] in ("plus", "plusplus"):
        return model(split["risk"], split["attr"], split["graph"], hyper, split["idx"], prior)
    emb = model[0](split["risk"], split["attr"], split["graph"], hyper, split["idx"], prior)
    return model[1](emb)


def arm_probabilities(arm: str, output) -> torch.Tensor:
    return output.probabilities if ARM_DEFS[arm]["kind"] in ("plus", "plusplus") else output.exp()


def _diagnostics(dataset: dict, split_name: str, result) -> dict[str, np.ndarray]:
    """Persist the uncertainty/conflict signals used by the mechanism analysis."""
    diagnostics = {
        "uncertainty": result.fused_uncertainty.cpu().numpy(),
        "conflict": result.conflict.cpu().numpy(),
        "fused_p": result.fused_probabilities.cpu().numpy(),
        "node_p": result.node_probabilities.cpu().numpy(),
        "graph_p": result.graph_probabilities.cpu().numpy(),
    }
    if hasattr(result, "contagion_conflict"):
        diagnostics["contagion_conflict"] = result.contagion_conflict.cpu().numpy()
        diagnostics["mutual_conflict"] = result.mutual_conflict.cpu().numpy()
        diagnostics["degree"] = result.degree.cpu().numpy().astype(np.float64)
    return diagnostics


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
    plusplus_kwargs: dict,
) -> tuple[dict, dict]:
    seed_everything(seed)
    model = make_arm(dataset, arm, device, plusplus_kwargs)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    kind = ARM_DEFS[arm]["kind"]
    loss_fn = (
        EvidentialRiskLoss(class_weights=class_weights) if kind in ("plus", "plusplus") else None
    )
    weight_tensor = (
        torch.tensor(class_weights, dtype=torch.float32, device=device)
        if class_weights is not None
        else None
    )

    splits = dataset["splits"]
    hypergraphs = arms_config["incidences"]
    priors = arms_config["priors"]
    use_prior = ARM_DEFS[arm]["use_prior"]
    prior_for = priors if use_prior else {name: None for name in SPLIT_ORDER}

    def run(split_name: str):
        return forward_arm(
            model, arm, splits[split_name], hypergraphs[split_name], prior_for[split_name]
        )

    train_y = torch.as_tensor(splits["train"]["y"], dtype=torch.long, device=device)
    valid_auc = -1.0
    best_state, best_epoch = None, 0
    started = time.monotonic()
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        result = run("train")
        if kind in ("plus", "plusplus"):
            # For RiskGNN++ result.fused_alpha is already degree-regularised, so the
            # degree-regularised likelihood is the standard marginal likelihood
            # evaluated at the budget-scaled evidence.
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
    model.eval()
    with torch.no_grad():
        for split_name in ("cal", "test"):
            result = run(split_name)
            probs = arm_probabilities(arm, result)
            predictions[f"{arm}_{split_name}_p"] = probs.cpu().numpy()
            metrics[split_name] = evaluate_risk_predictions(
                probs[:, 1].cpu().numpy(), splits[split_name]["y"]
            )
            if kind in ("plus", "plusplus"):
                for key, value in _diagnostics(dataset, split_name, result).items():
                    predictions[f"{arm}_{split_name}_{key}"] = value
                metrics[f"{split_name}_fused"] = evaluate_risk_predictions(
                    result.fused_probabilities[:, 1].cpu().numpy(),
                    splits[split_name]["y"],
                )
    info = {
        "best_valid_auc": valid_auc,
        "best_epoch": best_epoch,
        "seconds": time.monotonic() - started,
        "cal": metrics["cal"],
        "test": metrics["test"],
    }
    if "test_fused" in metrics:
        info["test_fused"] = metrics["test_fused"]
    return predictions, info


def topology_diagnostics(
    dataset: dict, arm: str, split_name: str, predictions: dict, conflict: np.ndarray
) -> dict:
    """Contrast model conflict with degree and label-level topology mismatch.

    Labels are used only here, for analysis; they never enter training.  A node's
    heterophily is the share of its incident neighbours whose label differs, i.e. a
    direct measurement of the "healthy firm inside a toxic cluster" situation.
    """
    split = dataset["splits"][split_name]
    edge_index = np.asarray(split["graph"][0], dtype=np.int64)
    source, target = edge_index[:, 0], edge_index[:, 1]

    # SMEsD edges reference person nodes after the company block; label them -1 and
    # exclude them from the heterophily statistics via the ``known`` mask.
    num_all = dataset["company_num"] + dataset.get("person_num", 0)
    labels_all = np.full(num_all, -1, dtype=np.int64)
    for name in ("train", "valid", "test"):
        part = dataset["splits"][name]
        labels_all[np.asarray(part["idx"], dtype=np.int64)] = np.asarray(part["y"], dtype=np.int64)

    degree = np.bincount(target, minlength=num_all)
    differs = (labels_all[source] != labels_all[target]).astype(np.float64)
    known = (labels_all[source] >= 0) & (labels_all[target] >= 0)
    hetero_sum = np.bincount(target, weights=differs * known, minlength=num_all)
    hetero_cnt = np.bincount(target, weights=known.astype(np.float64), minlength=num_all)

    idx = np.asarray(split["idx"], dtype=np.int64)
    node_degree = degree[idx].astype(np.float64)
    node_hetero = np.divide(
        hetero_sum[idx], hetero_cnt[idx], out=np.zeros(len(idx)), where=hetero_cnt[idx] > 0
    )

    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])

    def _spearman(a: np.ndarray, b: np.ndarray) -> float:
        from scipy.stats import spearmanr

        if len(a) < 3:
            return 0.0
        value = float(spearmanr(a, b).statistic)
        return value if np.isfinite(value) else 0.0

    probs = predictions[f"{arm}_{split_name}_p"][:, 1]
    labels = np.asarray(split["y"], dtype=np.int64)
    errors = ((probs >= 0.5).astype(np.int64) != labels).astype(np.float64)

    high = conflict >= np.quantile(conflict, 0.75)
    low = conflict <= np.quantile(conflict, 0.25)
    return {
        "conflict_degree_pearson": _corr(conflict, node_degree),
        "conflict_degree_spearman": _spearman(conflict, node_degree),
        "conflict_heterophily_pearson": _corr(conflict, node_hetero),
        "conflict_heterophily_spearman": _spearman(conflict, node_hetero),
        "conflict_error_pearson": _corr(conflict, errors),
        "error_rate_high_conflict": float(errors[high].mean()) if high.any() else 0.0,
        "error_rate_low_conflict": float(errors[low].mean()) if low.any() else 0.0,
        "mean_degree_high_conflict": float(node_degree[high].mean()) if high.any() else 0.0,
        "mean_degree_low_conflict": float(node_degree[low].mean()) if low.any() else 0.0,
        "mean_heterophily_high_conflict": float(node_hetero[high].mean()) if high.any() else 0.0,
        "mean_heterophily_low_conflict": float(node_hetero[low].mean()) if low.any() else 0.0,
    }


def _aggregate(rows: list[dict], arms: tuple[str, ...]) -> dict:
    summary: dict[str, dict[str, float]] = {}
    for arm in arms:
        arm_rows = [row for row in rows if row["arm"] == arm]
        for metric in ("rocAuc", "prAuc", "ece", "brier"):
            values = np.asarray([row[metric] for row in arm_rows], dtype=np.float64)
            summary.setdefault(arm, {})[metric] = {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            }
    return summary


def _write_markdown(summary: dict, path: Path, arms: tuple[str, ...]) -> None:
    label = {
        "comrisk": "ComRisk",
        "riskgnn": "RiskGNN (+community prior)",
        "plus": "RiskGNN+",
        "plusplus": "RiskGNN++ (ours)",
        "plusplus_nodiscount": "RiskGNN++ w/o discount",
        "plusplus_noreg": "RiskGNN++ w/o degree-reg",
    }
    lines = [
        "# ComRisk / RiskGNN / RiskGNN+ / RiskGNN++ 对照结果",
        "",
        "各训练种子测试集指标，均值 ± 样本标准差（ddof=1）。",
        "",
        "| 模型 | ROC-AUC | PR-AUC | ECE | Brier |",
        "| --- | --- | --- | --- | --- |",
    ]
    for arm in arms:
        stats = summary[arm]
        lines.append(
            f"| {label.get(arm, arm)} | "
            f"{stats['rocAuc']['mean']:.4f} ± {stats['rocAuc']['std']:.4f} | "
            f"{stats['prAuc']['mean']:.4f} ± {stats['prAuc']['std']:.4f} | "
            f"{stats['ece']['mean']:.4f} ± {stats['ece']['std']:.4f} | "
            f"{stats['brier']['mean']:.4f} ± {stats['brier']['std']:.4f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("uk", "smesd"), default="uk")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", default=list(DEFAULT_ARMS), choices=sorted(ARM_DEFS))
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
    parser.add_argument("--conflict-exponent", type=float, default=1.0)
    parser.add_argument("--degree-exponent", type=float, default=0.25)
    parser.add_argument("--degree-lambda", type=float, default=0.5)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    if args.epochs < 1 or args.eval_every < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("epochs/eval-every must be positive and seeds unique")
    if not 0 < args.epsilon < 1 or not np.isfinite(args.beta) or args.beta < 0:
        parser.error("Require epsilon in (0, 1) and finite beta >= 0")
    if args.output.exists():
        parser.error("Output already exists; use a new directory to preserve prior runs")

    data_dir = args.data_dir
    if data_dir is None:
        data_dir = Path("datasets/uk_dataset_v1" if args.dataset == "uk" else "datasets/smesd")
    args.output.mkdir(parents=True)
    torch.set_num_threads(args.threads)
    device = torch.device("cpu")

    dataset = load_dataset(
        args.dataset,
        data_dir,
        embed_seed=args.embed_seed,
        standardize=not args.no_standardize,
        calib_fraction=args.calib_fraction,
        calib_seed=args.calib_seed,
        max_nodes=args.max_nodes,
        uniform_weights=args.edge_weights == "uniform",
    )
    arms_config = {"incidences": build_incidences(dataset), "priors": build_priors(dataset)}
    class_weights = class_weights_for(dataset, args.class_weight)
    plusplus_kwargs = {
        "conflict_exponent": args.conflict_exponent,
        "degree_exponent": args.degree_exponent,
        "degree_likelihood_lambda": args.degree_lambda,
    }
    from smesd_benchmark.data import summarize as summarize_smesd
    from uk_benchmark.data import summarize as summarize_uk

    data_summary = summarize_smesd(dataset) if args.dataset == "smesd" else summarize_uk(dataset)
    print(json.dumps(data_summary, ensure_ascii=False, indent=2), flush=True)
    print(f"class_weights={class_weights} arms={args.arms}", flush=True)

    experiment_root = Path(__file__).resolve().parents[1]
    plus_root = experiment_root.parent / "riskgnn+"
    source_roots = {
        **{
            name: plus_root / name for name in ("riskgnn_plus", "smesd_uncertainty", "uk_benchmark")
        },
        **{
            name: experiment_root / name
            for name in ("riskgnn_pp", "smesd_benchmark", "riskgnn_benchmark")
        },
    }
    source_files = {
        f"{name}/{path.relative_to(directory)}": path
        for name, directory in source_roots.items()
        for path in sorted(directory.rglob("*.py"))
    }

    manifest = {
        "dataset": args.dataset,
        "data_dir": str(data_dir.resolve()),
        "data": data_summary,
        "data_sha256": dataset["source_sha256"],
        "class_weights": list(class_weights) if class_weights else None,
        "edge_weights": args.edge_weights,
        "arms": {arm: ARM_DEFS[arm] for arm in args.arms},
        "plusplus": plusplus_kwargs,
        "protocol": {
            "epochs": args.epochs,
            "lr": args.lr,
            "eval_every": args.eval_every,
            "grad_clip": 0.25,
            "scheduler": "cosine",
            "select": "best validation ROC-AUC",
        },
        "seeds": args.seeds,
        "torch": torch.__version__,
        "numpy": np.__version__,
        "device": "cpu",
        "source_sha256": {
            relative: hashlib.sha256(path.read_bytes()).hexdigest()
            for relative, path in source_files.items()
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
        shutil.copyfile(source_files[relative], target)

    rows: list[dict] = []
    audits: list[dict] = []
    topologies: dict[str, list[dict]] = {}
    for seed in args.seeds:
        seed_dir = args.output / f"seed_{seed}"
        seed_dir.mkdir()
        payload = {
            "seed": np.asarray(seed),
            "cal_y": dataset["splits"]["cal"]["y"],
            "test_y": dataset["splits"]["test"]["y"],
        }
        training: dict[str, dict] = {}
        for arm in args.arms:
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
                plusplus_kwargs,
            )
            payload.update(predictions)
            training[arm] = info
            rows.append(dict(info["test"], arm=arm, seed=seed, split="test"))
            if ARM_DEFS[arm]["kind"] == "plusplus":
                diagnostics = topology_diagnostics(
                    dataset, arm, "test", predictions, predictions[f"{arm}_test_conflict"]
                )
                topologies.setdefault(arm, []).append({"seed": seed, **diagnostics})
                print(f"[seed={seed}] {arm} topology:", flush=True)
                print(json.dumps(diagnostics, ensure_ascii=False), flush=True)
            if arm in {"plus", "plusplus"}:
                auditor = ConformalRiskAuditor(epsilon=args.epsilon, beta=args.beta)
                q_hat = auditor.calibrate(
                    predictions[f"{arm}_cal_p"],
                    predictions[f"{arm}_cal_uncertainty"],
                    payload["cal_y"],
                )
                audit = auditor.audit(
                    predictions[f"{arm}_test_p"],
                    predictions[f"{arm}_test_uncertainty"],
                    payload["test_y"],
                )
                auto = int(
                    sum(
                        decision in (AuditDecision.AUTO_APPROVE, AuditDecision.AUTO_REJECT)
                        for decision in audit.decisions
                    )
                )
                audits.append(
                    {
                        "seed": seed,
                        "arm": arm,
                        "q_hat": q_hat,
                        "coverage": audit.empirical_coverage,
                        "auto": auto,
                        "deferral_rate": audit.deferral_rate,
                        "ood_rate": audit.ood_rate,
                    }
                )
        np.savez_compressed(seed_dir / "predictions.npz", **payload)
        (seed_dir / "training.json").write_text(
            json.dumps(training, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        conflict_key = next(
            (f"{arm}_test_conflict" for arm in args.arms if f"{arm}_test_conflict" in payload),
            None,
        )
        if conflict_key is not None:
            strata = analyze_conflict_contagion(
                payload[conflict_key], payload["test_y"], quantiles=4
            )
            print(f"[seed={seed}] conflict strata ({conflict_key}):", flush=True)
            for row in strata:
                print(json.dumps(row, ensure_ascii=False), flush=True)

    summary = _aggregate(rows, tuple(args.arms))
    (args.output / "summary.json").write_text(
        json.dumps(
            {"test": summary, "rows": rows, "audits": audits, "topology": topologies},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_markdown(summary, args.output / "results.md", tuple(args.arms))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    (args.output / "COMPLETE").write_text("All requested seeds completed.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
