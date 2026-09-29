"""Train paired SMEsD uncertainty variants on one synthetic scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

HERE = Path(__file__).resolve().parent
RISK_GNN_DIR = HERE.parent / "riskgnn"
MODEL_SOURCE_FILES = {
    "trainer": Path(__file__).resolve(),
    "uncertaintyProtocol": HERE / "uncertainty_protocol.py",
    "riskgnnModel": RISK_GNN_DIR / "gnn.py",
    "riskgnnUtils": RISK_GNN_DIR / "utils.py",
}
sys.path.insert(0, str(RISK_GNN_DIR))

from gnn import RiskGNN
from uncertainty_protocol import (
    VARIANTS,
    build_directed_graph,
    load_scenario,
)
from utils import (
    Classifier,
    build_group_prior_feature,
    build_group_prior_feature_loo,
    build_incidence,
    fit_bayesian_group_prior,
    gen_attribute_hg,
    set_random_seed,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def best_f1_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(labels, probabilities)
    if len(thresholds) == 0:
        return 0.5
    denominator = precision[:-1] + recall[:-1]
    scores = np.divide(
        2 * precision[:-1] * recall[:-1],
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )
    return float(thresholds[int(np.argmax(scores))])


def classification_metrics(
    labels: np.ndarray, probabilities: np.ndarray, threshold: float
) -> dict[str, float]:
    predictions = probabilities >= threshold
    return {
        "rocAuc": float(roc_auc_score(labels, probabilities)),
        "prAuc": float(average_precision_score(labels, probabilities)),
        "brier": float(brier_score_loss(labels, probabilities)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "threshold": threshold,
    }


def predict(
    gnn: RiskGNN,
    classifier: Classifier,
    risk_data: object,
    company_attr: object,
    graph: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    hypergraph: object,
    indices: object,
    community_prior: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    embedding = gnn.forward(
        risk_data,
        company_attr,
        graph,
        hypergraph,
        indices,
        None,
        community_prior,
    )
    log_probability = classifier.forward(embedding)
    probability = log_probability.exp()[:, 1]
    return log_probability, probability.detach().cpu().numpy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--scenario-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--embedding-path", type=Path)
    parser.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--n-epoch", type=int, default=500)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--clip", type=float, default=0.25)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--hyper-impl", choices=("scipy", "vectorized"), default="scipy"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    data_dir = args.data_dir.resolve()
    scenario_dir = args.scenario_dir.resolve()
    output_dir = args.output_dir.resolve()
    embedding_path = (
        args.embedding_path.resolve()
        if args.embedding_path is not None
        else data_dir / "meta_emb.pkl"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_manifest = json.loads((scenario_dir / "manifest.json").read_text())
    for source in scenario_manifest["sourceFiles"].values():
        source_path = data_dir / source["file"]
        if file_sha256(source_path) != source["sha256"]:
            raise ValueError(f"source data hash differs from scenario: {source_path}")
    for split in ("train", "valid", "test"):
        scenario_path = scenario_dir / f"{split}_pairs.npz"
        if file_sha256(scenario_path) != scenario_manifest["splits"][split]["sha256"]:
            raise ValueError(
                f"scenario file hash differs from manifest: {scenario_path}"
            )

    train_data = pd.read_pickle(data_dir / "train_data.pkl")
    valid_data = pd.read_pickle(data_dir / "validate_data.pkl")
    test_data = pd.read_pickle(data_dir / "test_data.pkl")
    train_indices, valid_indices, test_indices = pd.read_pickle(
        data_dir / "split_data_idx.pkl"
    )
    company_embedding, person_embedding = pd.read_pickle(embedding_path)
    company_count = len(company_embedding)
    person_count = len(person_embedding)

    train_risk, train_attr, _, train_hyper_raw, train_label = train_data
    valid_risk, valid_attr, _, valid_hyper_raw, valid_label = valid_data
    test_risk, test_attr, _, test_hyper_raw, test_label = test_data
    labels = {
        "train": np.asarray(train_label, dtype=np.int64),
        "valid": np.asarray(valid_label, dtype=np.int64),
        "test": np.asarray(test_label, dtype=np.int64),
    }

    scenarios = {
        split: load_scenario(scenario_dir / f"{split}_pairs.npz")
        for split in ("train", "valid", "test")
    }
    graphs = {
        split: build_directed_graph(
            scenario, args.variant, args.seed, args.confidence_threshold
        )
        for split, scenario in scenarios.items()
    }
    hypergraph_builder = (
        (lambda raw: build_incidence(company_count, raw))
        if args.hyper_impl == "vectorized"
        else (lambda raw: gen_attribute_hg(company_count, raw, X=None))
    )
    hypergraphs = {
        split: [hypergraph_builder(raw[name]) for name in ("industry", "area", "qualify")]
        for split, raw in (
            ("train", train_hyper_raw),
            ("valid", valid_hyper_raw),
            ("test", test_hyper_raw),
        )
    }

    use_prior = bool(VARIANTS[args.variant]["use_prior"])
    priors: dict[str, np.ndarray | None] = {
        "train": None,
        "valid": None,
        "test": None,
    }
    prior_metadata: dict[str, float | int] | None = None
    if use_prior:
        group_prior, alpha, beta, global_mean, group_stats = fit_bayesian_group_prior(
            train_hyper_raw["area"], train_label, train_indices
        )
        priors = {
            "train": build_group_prior_feature_loo(
                train_hyper_raw["area"],
                train_indices,
                train_label,
                group_stats,
                alpha,
                beta,
                global_mean,
            ),
            "valid": build_group_prior_feature(
                valid_hyper_raw["area"], valid_indices, group_prior, global_mean
            ),
            "test": build_group_prior_feature(
                test_hyper_raw["area"], test_indices, group_prior, global_mean
            ),
        }
        prior_metadata = {
            "alpha": float(alpha),
            "beta": float(beta),
            "globalMean": float(global_mean),
            "groups": len(group_prior),
        }

    set_random_seed(args.seed)
    requested_device = args.device
    if requested_device == "auto":
        requested_device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(requested_device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    gnn = RiskGNN(
        16,
        12,
        company_count,
        person_count,
        12,
        11,
        device,
        company_embedding,
        person_embedding,
        4,
        4,
        5,
        use_hypergraph=True,
        use_edgegraph=True,
        hyper_impl=args.hyper_impl,
        use_community_prior=use_prior,
    )
    classifier = Classifier(12, 2)
    model = torch.nn.Sequential(gnn, classifier).to(device)
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)

    best_epoch = -1
    best_auc = -np.inf
    best_loss = np.inf
    best_state: dict[str, torch.Tensor] | None = None
    for epoch in range(args.n_epoch):
        epoch_started = time.time()
        model.train()
        train_log_probability, _ = predict(
            gnn,
            classifier,
            train_risk,
            train_attr,
            graphs["train"],
            hypergraphs["train"],
            train_indices,
            priors["train"],
        )
        train_loss = criterion(
            train_log_probability,
            torch.as_tensor(labels["train"], dtype=torch.long, device=device),
        )
        optimizer.zero_grad()
        train_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.clip)
        optimizer.step()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            valid_log_probability, valid_probability = predict(
                gnn,
                classifier,
                valid_risk,
                valid_attr,
                graphs["valid"],
                hypergraphs["valid"],
                valid_indices,
                priors["valid"],
            )
            valid_loss = float(
                criterion(
                    valid_log_probability,
                    torch.as_tensor(labels["valid"], dtype=torch.long, device=device),
                ).item()
            )
            valid_auc = float(roc_auc_score(labels["valid"], valid_probability))
        improved = valid_auc > best_auc + 1e-12 or (
            abs(valid_auc - best_auc) <= 1e-12 and valid_loss < best_loss
        )
        if improved:
            best_epoch = epoch
            best_auc = valid_auc
            best_loss = valid_loss
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
        print(
            f"epoch={epoch} seconds={time.time() - epoch_started:.3f} "
            f"train_loss={train_loss.item():.6f} valid_loss={valid_loss:.6f} "
            f"valid_auc={valid_auc:.6f} update={int(improved)}",
            flush=True,
        )

    if best_state is None:
        raise RuntimeError("training did not produce a checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        _, valid_probability = predict(
            gnn,
            classifier,
            valid_risk,
            valid_attr,
            graphs["valid"],
            hypergraphs["valid"],
            valid_indices,
            priors["valid"],
        )
        _, test_probability = predict(
            gnn,
            classifier,
            test_risk,
            test_attr,
            graphs["test"],
            hypergraphs["test"],
            test_indices,
            priors["test"],
        )

    threshold = best_f1_threshold(labels["valid"], valid_probability)
    valid_metrics = classification_metrics(
        labels["valid"], valid_probability, threshold
    )
    test_metrics = classification_metrics(labels["test"], test_probability, threshold)
    result = {
        "protocolVersion": 2,
        "variant": args.variant,
        "variantConfig": VARIANTS[args.variant],
        "seed": args.seed,
        "epochs": args.n_epoch,
        "bestEpoch": best_epoch,
        "selectionMetric": "validation_roc_auc",
        "confidenceThreshold": args.confidence_threshold,
        "hyperImpl": args.hyper_impl,
        "parameterCount": sum(parameter.numel() for parameter in model.parameters()),
        "runtimeSeconds": time.time() - started,
        "device": str(device),
        "torchVersion": torch.__version__,
        "cudaVersion": torch.version.cuda,
        "cudaDevice": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else None
        ),
        "embeddingPath": str(embedding_path),
        "embeddingSha256": file_sha256(embedding_path),
        "embeddingManifestSha256": (
            file_sha256(embedding_path.parent / "manifest.json")
            if (embedding_path.parent / "manifest.json").exists()
            else None
        ),
        "sourceSha256": {
            name: file_sha256(path) for name, path in MODEL_SOURCE_FILES.items()
        },
        "scenarioManifestSha256": file_sha256(scenario_dir / "manifest.json"),
        "scenario": {
            "schemaVersion": scenario_manifest["schemaVersion"],
            "simulationSeed": scenario_manifest["simulationSeed"],
            "noiseRatio": scenario_manifest["noiseRatio"],
        },
        "directedEdges": {split: len(graph[1]) for split, graph in graphs.items()},
        "prior": prior_metadata,
        "validation": valid_metrics,
        "test": test_metrics,
    }
    torch.save(
        {"state_dict": model.state_dict(), "result": result}, output_dir / "model.pt"
    )
    np.savez_compressed(
        output_dir / "predictions.npz",
        valid_id=np.asarray(valid_indices, dtype=np.int64),
        valid_label=labels["valid"],
        valid_probability=valid_probability,
        test_id=np.asarray(test_indices, dtype=np.int64),
        test_label=labels["test"],
        test_probability=test_probability,
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("FINAL_METRICS_JSON=" + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
