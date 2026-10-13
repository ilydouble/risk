"""Train the actual RiskGNN+ evidence model on adapter-owned bounded graphs."""

import hashlib
import platform
import shutil
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch

from riskgnn.workbench.artifacts import read_json, seal, verify, write_json
from riskgnn.workbench.training import code_version
from riskgnn_plus.loss import EvidentialRiskLoss
from riskgnn_plus.workbench.network import PortablePlus
from riskgnn_plus.workbench.preparation import FORMAT


def source_version() -> str:
    root = Path(__file__).resolve().parents[2]
    fingerprint = hashlib.sha256(code_version().encode())
    for directory in (root / "riskgnn_plus", root / "smesd_uncertainty/comrisk_base"):
        for source in sorted(directory.rglob("*.py")):
            fingerprint.update(str(source.relative_to(root)).encode())
            fingerprint.update(source.read_bytes())
    return fingerprint.hexdigest()


def train(prepared: Path, output: Path, epochs: int, *, configuration=None, metric_callback=None):
    verify(prepared, "riskgnn-prepared-v1")
    if not 1 <= epochs <= 20:
        raise ValueError("epochs must be between 1 and 20")
    torch.set_num_threads(2)
    torch.manual_seed(0)
    np.random.seed(0)
    torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True, exist_ok=True)
    for file in prepared.iterdir():
        if file.is_file() and file.name != "manifest.json":
            shutil.copy2(file, output / file.name)
    meta = read_json(output / "metadata.json")
    context = dict(np.load(output / "context.npz", allow_pickle=False))
    model = PortablePlus(meta, context, read_json(output / "risk_events.json"))
    train_nodes = np.where(context["splits"] == "train")[0].tolist()
    validation = np.where(context["splits"] == "val")[0].tolist()
    if not train_nodes or not validation:
        raise ValueError("Training and validation targets are required")
    positives = int(context["labels"][train_nodes].sum())
    negatives = len(train_nodes) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("Training requires both labels")
    weights = (1.0, negatives / positives)
    loss_fn = EvidentialRiskLoss(class_weights=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs, eta_min=1e-6)
    # Warm graph caches before training so constructor RNG does not alter epoch execution.
    for snapshot in sorted(set(map(str, context["snapshots"]))):
        model.graph(snapshot)
    history, best = [], float("inf")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        result = model(train_nodes)
        loss = loss_fn(
            result.fused_alpha,
            result.node_alpha,
            result.graph_alpha,
            torch.tensor(context["labels"][train_nodes]),
            primary_logits=result.primary_logits,
            kl_annealing=min(1.0, (epoch + 1) / 10),
        )["loss"]
        if not torch.isfinite(loss):
            raise ValueError("Non-finite RiskGNN+ training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
        optimizer.step()
        scheduler.step()
        model.eval()
        with torch.inference_mode():
            prediction = model(validation)
            validation_loss = float(
                torch.nn.functional.cross_entropy(
                    prediction.primary_logits,
                    torch.tensor(context["labels"][validation]),
                )
            )
        if not np.isfinite(validation_loss):
            raise ValueError("Non-finite RiskGNN+ validation loss")
        row = {
            "epoch": epoch + 1,
            "trainLoss": float(loss.detach()),
            "validationLoss": validation_loss,
        }
        history.append(row)
        if metric_callback:
            metric_callback(row)
        if validation_loss < best:
            best = validation_loss
            torch.save(model.state_dict(), output / "weights.pt")
            meta["selectedEpoch"] = epoch + 1
    meta.update(
        {
            "runnerId": "riskgnn",
            "epochs": epochs,
            "history": history,
            "threshold": 0.5,
            "python": platform.python_version(),
            "torch": torch.__version__,
            "codeVersion": source_version(),
            "predictionSource": "primary_classifier",
            "loss": {
                "name": "EvidentialRiskLoss",
                "classWeights": list(weights),
                "fitSplit": "train",
                "gammaNode": 0.3,
                "gammaGraph": 0.3,
                "klWeight": 0.001,
            },
            "calibration": "not_fitted",
            "conformal": "not_fitted",
            "dependencies": {
                name: version(name)
                for name in ("torch", "torch-geometric", "numpy", "scikit-learn")
            },
        }
    )
    if configuration is not None:
        meta["configuration"] = configuration
        meta["effectiveConfig"] = configuration["resolvedParameters"]
    meta["actualCounts"] = {
        "targets": meta["targetCount"],
        "train": meta["splitCounts"]["train"],
        "validation": meta["splitCounts"]["val"],
        "test": meta["splitCounts"]["test"],
    }
    meta["experimentProfile"] = {
        "version": 1,
        "algorithm": "RiskGNN+",
        "threshold": 0.5,
        "evaluationSplit": "test",
        "artifactFormat": FORMAT,
        "device": "cpu",
        "runnerId": "riskgnn",
        "datasetFormat": meta["datasetFormat"],
        "datasetSha256": meta["sourceSha256"],
        "taskType": meta["taskType"],
        "target": meta["target"],
        "seed": meta["seed"],
        "selectedFeatures": meta["features"],
        "preprocessing": meta["preprocessing"],
        "splits": meta["splitCounts"],
        "profile": meta["profile"],
        "epochs": epochs,
        "selectionMetric": "validation_loss",
        "selectedEpoch": meta["selectedEpoch"],
        "codeVersion": meta["codeVersion"],
        "dependencies": meta["dependencies"],
        "graph": {
            "enabled": True,
            "nodes": meta["nodeCount"],
            "edges": meta["edgeCount"],
            "hyperedges": meta["hyperedgeCount"],
            "incidences": meta["incidenceCount"],
            "events": meta["eventCount"],
            "edgePolicy": meta["edgePolicy"],
            "hypergraphPolicy": meta["hypergraphPolicy"],
            "usedInputs": meta["usedInputs"],
            "retainedOnlyInputs": meta["retainedOnlyInputs"],
            "evaluation": meta.get("evaluation", "static_transductive"),
            "embeddingSource": meta["embeddingSource"],
            "predictionSource": meta["predictionSource"],
        },
    }
    write_json(output / "metadata.json", meta)
    seal(output, kind=FORMAT, metadata={"sourceSha256": meta["sourceSha256"]})
    return meta
