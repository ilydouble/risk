import hashlib
import json
import platform
import shutil
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from riskgnn.training_engine import run_epochs
from riskgnn.workbench.artifacts import read_json, seal, verify, write_json
from riskgnn.workbench.network import EdgeRiskGNN
from riskgnn.workbench.predictor import Predictor
from riskgnn.workbench.sampling import Sampler


def emit(kind: str, **data: Any) -> None:
    print(json.dumps({"kind": kind, "data": data}, allow_nan=False), flush=True)


def code_version() -> str:
    source = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    # Keep local virtual environments, tests and deployment-only files out of model identity.
    files = list((source / "dataset_adapters").rglob("*.py"))
    files += list((source / "workbench").rglob("*.py"))
    files += [
        source / name
        for name in (
            "gnn.py",
            "utils.py",
            "train_sg_neighbor.py",
            "training_engine.py",
            "workbench_cli.py",
        )
    ]
    for file in sorted(files):
        digest.update(str(file.relative_to(source)).encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def metrics(y: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    prediction = score >= 0.5
    both = len(np.unique(y)) == 2
    fpr, tpr, _ = roc_curve(y, score) if both else ([], [], [])
    return {
        "count": len(y),
        "positiveCount": int(y.sum()),
        "rocAuc": float(roc_auc_score(y, score)) if both else None,
        "prAuc": float(average_precision_score(y, score)) if both else None,
        "ks": float(np.max(tpr - fpr)) if both else None,
        "brier": float(brier_score_loss(y, score)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "confusionMatrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
    }


def train(
    prepared: Path,
    output: Path,
    epochs: int = 2,
    *,
    runner_id: str = "riskgnn",
    metric_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if runner_id != "riskgnn":
        raise ValueError("Only RiskGNN is deployed in this workbench")
    verify(prepared, "riskgnn-prepared-v1")
    if not 1 <= epochs <= 20:
        raise ValueError("epochs must be between 1 and 20")
    torch.set_num_threads(2)
    torch.manual_seed(0)
    np.random.seed(0)
    torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("context.npz", "ids.json", "metadata.json"):
        shutil.copy2(prepared / name, output / name)
    meta = read_json(output / "metadata.json")
    context = dict(np.load(output / "context.npz", allow_pickle=False))
    meta["runnerId"] = runner_id
    meta["sourceEdgeCount"] = meta["edgeCount"]
    meta["edgeCount"] = len(context["edges"])
    x = torch.tensor(context["features"])
    labels = torch.tensor(context["labels"])
    train_nodes = np.where(context["splits"] == "train")[0]
    validation = np.where(context["splits"] == "val")[0]
    ids = read_json(output / "ids.json")
    sampler = Sampler(context["edges"], len(ids))
    model = EdgeRiskGNN(len(ids), len(meta["relations"]))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)
    best = float("inf")
    history = []

    def batches(epoch):
        nodes = np.random.default_rng(epoch).permutation(train_nodes)
        return [nodes[start : start + 64] for start in range(0, len(nodes), 64)]

    def forward(epoch, batch):
        n, edges, types = sampler.sample(batch.tolist(), epoch * 100 + int(batch[0]))
        if len(n) < 2:
            raise ValueError("Training requires at least two nodes per batch")
        return model(x, n, edges, types, len(batch)), labels[batch]

    def on_epoch(epoch, loss, _count, _duration):
        nonlocal best
        model.eval()
        with torch.inference_mode():
            probabilities = []
            for node in validation:
                n, edges, types = sampler.sample([int(node)], int(node) + 999999)
                probabilities.append(float(model(x, n, edges, types, 1)[0, 1].exp()))
        p = np.clip(probabilities, 1e-7, 1 - 1e-7)
        y = context["labels"][validation]
        validation_loss = float(np.mean(-y * np.log(p) - (1 - y) * np.log(1 - p)))
        row = {
            "epoch": epoch + 1,
            "trainLoss": loss,
            "validationLoss": validation_loss,
        }
        history.append(row)
        if metric_callback is None:
            emit("metric", **row)
        else:
            metric_callback(row)
        if validation_loss < best:
            best = validation_loss
            torch.save(model.state_dict(), output / "weights.pt")
            meta["selectedEpoch"] = epoch + 1

    run_epochs(
        model,
        optimizer,
        scheduler,
        torch.nn.functional.cross_entropy,
        epochs,
        batches,
        forward,
        on_epoch,
    )
    meta.update(
        {
            "epochs": epochs,
            "history": history,
            "threshold": 0.5,
            "architecture": "sg-node-edge-v2",
            "python": platform.python_version(),
            "torch": torch.__version__,
            "codeVersion": code_version(),
            "dependencies": {
                name: version(name)
                for name in ("torch", "torch-geometric", "numpy", "scikit-learn")
            },
        }
    )
    meta["experimentProfile"] = {
        "version": 1,
        "threshold": 0.5,
        "evaluationSplit": "test",
        "artifactFormat": "riskgnn-model-v2",
        "device": "cpu",
        "runnerId": runner_id,
        "datasetFormat": "sg-comrisk-v1",
        "datasetSha256": meta["sourceSha256"],
        "taskType": "entity_snapshot",
        "target": "Singapore corporate distress proxy",
        "seed": meta["seed"],
        "selectedFeatures": meta["features"],
        "preprocessing": meta["preprocessing"],
        "splits": meta["splitCounts"],
        "profile": meta["profile"],
        "epochs": epochs,
        "graph": {
            "enabled": True,
            "nodes": len(ids),
            "edges": len(context["edges"]),
        },
        "selectionMetric": "validation_loss",
        "selectedEpoch": meta["selectedEpoch"],
        "codeVersion": meta["codeVersion"],
        "dependencies": meta["dependencies"],
    }
    write_json(output / "metadata.json", meta)
    seal(output, kind="riskgnn-model-v2", metadata={"sourceSha256": meta["sourceSha256"]})
    return meta


def evaluate(model_dir: Path, *, output: Path | None = None) -> dict[str, Any]:
    torch.set_num_threads(2)
    predictor = Predictor(model_dir)
    indices = np.where(predictor.context["splits"] == "test")[0]
    rows = predictor.predict([predictor.ids[i] for i in indices])
    scores = np.array([row["probability"] for row in rows])
    report = {
        "split": "test",
        "independentReload": True,
        "metrics": metrics(predictor.context["labels"][indices], scores),
        "sourceSha256": predictor.meta["sourceSha256"],
    }
    destination = output if output is not None else model_dir
    write_json(destination / "metrics.json", report)
    write_json(destination / "predictions.json", rows)
    if output is None:
        # Preserve the original CLI; adapter evaluations write separate immutable reports.
        seal(
            model_dir,
            kind="riskgnn-model-v2",
            metadata={"sourceSha256": predictor.meta["sourceSha256"]},
        )
    return report
