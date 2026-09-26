from __future__ import annotations

import copy
import hashlib
import random
import time
from pathlib import Path

import numpy as np
import torch
from com_risk_runtime.model import ComRisk
from com_risk_runtime.preprocessing import tensorize
from com_risk_runtime.prior import add_prior
from com_risk_runtime.schema import Dataset
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from torch.nn import functional as F

from .data import dump_json, fit_preprocessor
from .pretrain import pretrain
from .prior import fit_prior


def metrics(y, p, threshold=0.5):
    y, p = np.asarray(y), np.asarray(p)
    both = len(np.unique(y)) == 2
    fpr, tpr, _ = roc_curve(y, p) if both else (None, None, None)
    pred = p >= threshold
    order = np.argsort(-p, kind="stable")
    k10, k5 = max(1, int(np.ceil(len(y) * 0.1))), max(1, int(np.ceil(len(y) * 0.05)))
    bins = []
    for i in range(10):
        mask = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        if mask.any():
            bins.append(
                {
                    "lower": i / 10,
                    "count": int(mask.sum()),
                    "mean_prediction": float(p[mask].mean()),
                    "observed_rate": float(y[mask].mean()),
                }
            )
    return {
        "n": len(y),
        "positives": int(np.sum(y)),
        "threshold": float(threshold),
        "roc_auc": float(roc_auc_score(y, p)) if both else None,
        "pr_auc": float(average_precision_score(y, p)) if both else None,
        "ks": float(np.max(tpr - fpr)) if tpr is not None and fpr is not None else None,
        "brier": float(brier_score_loss(y, p)),
        "lift_at_10pct": float(y[order[:k10]].mean() / y.mean()) if y.sum() else None,
        "capture_at_5pct": float(y[order[:k5]].sum() / y.sum()) if y.sum() else None,
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "calibration_curve": bins,
    }


def select_threshold(y, p):
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[np.argmax(f1)])


def load_data(path):
    path = Path(path)
    if path.is_dir():
        return {s: Dataset.read(path / f"{s}.json") for s in ("train", "valid", "test")}
    return Dataset.read(path)


def train(
    data,
    output,
    epochs=100,
    patience=15,
    seed=42,
    hidden=32,
    layers=2,
    mode="full",
    use_prior=True,
    pretrain_epochs=0,
):
    if min(epochs, patience, hidden, layers) < 1 or pretrain_epochs < 0:
        raise ValueError("invalid positive training parameters")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    datasets = data if isinstance(data, dict) else {s: data for s in ("train", "valid", "test")}
    source = datasets["train"]
    schema = {k: getattr(source, k) for k in ("feature_names", "relation_names", "hyperedge_types")}
    for s, d in datasets.items():
        if (
            any(getattr(d, k) != v for k, v in schema.items())
            or d.target_description != source.target_description
        ):
            raise ValueError("snapshot schema/target mismatch")
        if isinstance(data, dict) and any(n.split not in (None, s) for n in d.nodes):
            raise ValueError("snapshot contains labels assigned to another split")
    if isinstance(data, dict):
        ids = [
            {n.id for n in datasets[s].nodes if n.kind == "company"}
            for s in ("train", "valid", "test")
        ]
        if any(ids[i] & ids[j] for i in range(3) for j in range(i)):
            raise ValueError("company overlap across isolated snapshots")
    preprocessor = fit_preprocessor(source)
    prior = fit_prior(source, seed) if use_prior else None
    graphs = {s: tensorize(d, preprocessor) for s, d in datasets.items()}
    for s, g in graphs.items():
        if prior:
            add_prior(g, datasets[s], prior)
        mask = g["masks"][s]
        if mask.sum() == 0 or len(torch.unique(g["y"][mask])) != 2:
            raise ValueError(f"{s} requires both classes")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    config = {
        "feature_dim": len(source.feature_names),
        "relation_count": len(source.relation_names),
        "hyperedge_count": len(source.hyperedge_types),
        "hidden": hidden,
        "layers": layers,
        "dropout": 0.15,
        "use_prior": use_prior,
    }
    model = ComRisk(**config)
    pretrain_history = pretrain(model, graphs["train"], pretrain_epochs) if pretrain_epochs else []
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    best_loss, best_state, best_epoch, wait = float("inf"), None, 0, 0
    history = []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        graph = graphs["train"]
        mask = graph["masks"]["train"]
        loss = F.binary_cross_entropy_with_logits(model(graph, mode)[mask], graph["y"][mask])
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        model.eval()
        graph = graphs["valid"]
        mask = graph["masks"]["valid"]
        with torch.no_grad():
            valid_loss = F.binary_cross_entropy_with_logits(
                model(graph, mode)[mask], graph["y"][mask]
            ).item()
        history.append({"epoch": epoch, "train_loss": loss.item(), "valid_loss": valid_loss})
        if valid_loss < best_loss - 1e-6:
            best_loss, best_epoch, wait = valid_loss, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            wait += 1
        if epoch == 1 or epoch % 10 == 0:
            print(
                f"epoch={epoch} train_loss={loss.item():.4f} valid_loss={valid_loss:.4f}",
                flush=True,
            )
        if wait >= patience:
            break
    assert (
        best_state is not None
    )  # epochs is positive and the first validation loss must be finite.
    model.load_state_dict(best_state)
    model.eval()
    logits, labels = {}, {}
    with torch.no_grad():
        for s, g in graphs.items():
            mask = g["masks"][s]
            logits[s] = model(g, mode)[mask].numpy()
            labels[s] = g["y"][mask].numpy()
    # Fit only an intercept on validation; preserves ranking and can correct prevalence bias.
    offset = torch.zeros(1, requires_grad=True)
    calibration_optimizer = torch.optim.LBFGS([offset], max_iter=50, line_search_fn="strong_wolfe")

    def closure():
        calibration_optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(
            torch.tensor(logits["valid"]) + offset, torch.tensor(labels["valid"])
        )
        loss.backward()
        return loss

    calibration_optimizer.step(closure)
    intercept = float(offset.detach())
    probabilities = {
        s: torch.sigmoid(torch.tensor(v) + intercept).numpy() for s, v in logits.items()
    }
    threshold = select_threshold(labels["valid"], probabilities["valid"])
    results = {s: metrics(labels[s], probabilities[s], threshold) for s in graphs}
    raw_results = {
        s: metrics(labels[s], torch.sigmoid(torch.tensor(v)).numpy()) for s, v in logits.items()
    }
    baselines = {}
    for name, baseline in [
        ("logistic", LogisticRegression(max_iter=2000, random_state=seed)),
        (
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, random_state=seed),
        ),
    ]:
        x = {s: g["x"][g["masks"][s]].numpy() for s, g in graphs.items()}
        baseline.fit(x["train"], labels["train"])
        bp = {s: baseline.predict_proba(v)[:, 1] for s, v in x.items()}
        bt = select_threshold(labels["valid"], bp["valid"])
        baselines[name] = {s: metrics(labels[s], bp[s], bt) for s in graphs}
    hashes = {
        s: hashlib.sha256(d.model_dump_json().encode()).hexdigest() for s, d in datasets.items()
    }
    metadata = {
        "version": 2,
        "model": "ComRisk-Gated-v1",
        "config": config,
        "schema": schema,
        "preprocessor": preprocessor,
        "prior": prior,
        "threshold": threshold,
        "seed": seed,
        "mode": mode,
        "synthetic": source.synthetic,
        "dataset": source.name,
        "evaluation": source.evaluation,
        "target_description": source.target_description,
        "best_epoch": best_epoch,
        "dataset_sha256": hashes,
        "calibrated": True,
        "calibration": {"method": "validation_intercept", "intercept": intercept},
        "pretrain_epochs": pretrain_epochs,
        "torch_version": str(torch.__version__),
    }
    torch.save(best_state, output / "weights.pt")
    dump_json(output / "metadata.json", metadata)
    report = {
        "metadata": {k: v for k, v in metadata.items() if k not in {"prior", "preprocessor"}},
        "model": results,
        "uncalibrated": raw_results,
        "baselines": baselines,
        "history": history,
        "pretrain_history": pretrain_history,
        "elapsed_seconds": time.perf_counter() - started,
        "notes": [
            "Public benchmark: not Southeast Asian competition performance or fixed-horizon PD.",
            "Validation reused for early stopping, intercept and threshold; "
            "only test metrics are held out.",
            "Industry priors use OOF training labels and enter only the prediction head.",
            "Original outcome-relative event timing cannot establish strict "
            "point-in-time validity.",
        ],
    }
    dump_json(output / "metrics.json", report)
    return report
