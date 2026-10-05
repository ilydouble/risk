"""Pretrain a non-destructive, scenario-specific SMEsD MetaPath2Vec embedding."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch_geometric.nn import MetaPath2Vec
from .protocol import NODE_TYPES, build_metapath_graph, load_scenario

METAPATH_RELATIONS = (0, 1, 2, 3, 4, 5, 6, 7, 9, 8, 10, 11)
METAPATH = [
    (NODE_TYPES[relation][0], f"relation_{relation}", NODE_TYPES[relation][1])
    for relation in METAPATH_RELATIONS
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def graph_sha256(
    edges: dict[int, np.ndarray], confidence: dict[int, np.ndarray]
) -> str:
    digest = hashlib.sha256()
    for relation in range(12):
        values = np.ascontiguousarray(edges[relation], dtype=np.int64)
        digest.update(relation.to_bytes(2, "little"))
        digest.update(values.shape[0].to_bytes(8, "little"))
        digest.update(values.tobytes())
        digest.update(
            np.ascontiguousarray(confidence[relation], dtype=np.float32).tobytes()
        )
    return digest.hexdigest()


class ConfidenceMetaPath2Vec(MetaPath2Vec):
    """MetaPath2Vec with confidence-weighted positive random walks."""

    def __init__(
        self,
        edge_index_dict: dict[tuple[str, str, str], torch.Tensor],
        edge_confidence_dict: dict[tuple[str, str, str], torch.Tensor],
        confidence_alpha: float,
        **kwargs: object,
    ) -> None:
        super().__init__(edge_index_dict, **kwargs)
        self.confidence_prefix_dict: dict[tuple[str, str, str], torch.Tensor] = {}
        for edge_type, confidence in edge_confidence_dict.items():
            expected_count = len(self.col_dict[edge_type])
            if len(confidence) != expected_count:
                raise ValueError(f"confidence length differs for {edge_type}")
            weight = confidence.to(torch.float32).clamp_min(1e-12).pow(confidence_alpha)
            self.confidence_prefix_dict[edge_type] = weight.cumsum(dim=0)

    def _weighted_sample(
        self, edge_type: tuple[str, str, str], subset: torch.Tensor
    ) -> torch.Tensor:
        rowptr = self.rowptr_dict[edge_type]
        col = self.col_dict[edge_type]
        prefix = self.confidence_prefix_dict[edge_type]
        if col.numel() == 0:
            return torch.full_like(subset, self.dummy_idx)

        invalid = subset >= self.dummy_idx
        subset = subset.clamp(min=0, max=rowptr.numel() - 2)
        start = rowptr[subset]
        end = rowptr[subset + 1]
        count = end - start
        lower = torch.zeros(len(subset), dtype=prefix.dtype)
        has_previous = start > 0
        lower[has_previous] = prefix[start[has_previous] - 1]
        upper = prefix[(end - 1).clamp_min(0)]
        target = lower + torch.rand(len(subset), dtype=prefix.dtype) * (upper - lower)
        sampled_index = torch.searchsorted(prefix, target, right=True).clamp_max(
            col.numel() - 1
        )
        sampled = col[sampled_index]
        sampled[invalid | (count == 0)] = self.dummy_idx
        return sampled

    def _pos_sample(self, batch: torch.Tensor) -> torch.Tensor:
        batch = batch.repeat(self.walks_per_node)
        walks = [batch]
        for index in range(self.walk_length):
            edge_type = self.metapath[index % len(self.metapath)]
            batch = self._weighted_sample(edge_type, batch)
            walks.append(batch)

        random_walk = torch.stack(walks, dim=-1)
        random_walk.add_(self.offset.view(1, -1))
        random_walk[random_walk > self.dummy_idx] = self.dummy_idx
        contexts = []
        count = 1 + self.walk_length + 1 - self.context_size
        for index in range(count):
            contexts.append(random_walk[:, index : index + self.context_size])
        return torch.cat(contexts, dim=0)


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return device


def needs_weighted_sampler(
    confidence: dict[int, np.ndarray], confidence_mode: str, confidence_alpha: float
) -> bool:
    """Return whether confidence changes any within-relation transition odds."""
    if confidence_mode == "ignore" or confidence_alpha == 0:
        return False
    return any(
        len(values) > 1 and not np.equal(values, values[0]).all()
        for values in confidence.values()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--scenario-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--graph-mode", choices=("oracle", "all", "filter"), required=True)
    parser.add_argument(
        "--confidence-mode",
        choices=("ignore", "gate", "shuffle", "invert"),
        default="ignore",
    )
    parser.add_argument("--confidence-alpha", type=float, default=1.0)
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--walk-length", type=int, default=50)
    parser.add_argument("--context-size", type=int, default=5)
    parser.add_argument("--walks-per-node", type=int, default=5)
    parser.add_argument("--negative-samples", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    data_dir = args.data_dir.resolve()
    scenario_dir = args.scenario_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "meta_emb.pkl"
    source_embedding = data_dir / "meta_emb.pkl"
    if output_path == source_embedding:
        raise ValueError("refusing to overwrite the source SMEsD embedding")

    original_company, original_person = pd.read_pickle(source_embedding)
    company_count = len(original_company)
    person_count = len(original_person)
    scenarios = {
        split: load_scenario(scenario_dir / f"{split}_pairs.npz")
        for split in ("train", "valid", "test")
    }
    if args.confidence_alpha < 0:
        raise ValueError("confidence-alpha must be non-negative")
    edges, edge_confidence = build_metapath_graph(
        scenarios,
        args.graph_mode,
        args.confidence_mode,
        args.seed,
        args.confidence_threshold,
        company_count,
        person_count,
    )
    graph_hash = graph_sha256(edges, edge_confidence)
    edge_index_dict = {
        (
            NODE_TYPES[relation][0],
            f"relation_{relation}",
            NODE_TYPES[relation][1],
        ): torch.from_numpy(values.T.copy())
        for relation, values in edges.items()
    }
    edge_confidence_dict = {
        (
            NODE_TYPES[relation][0],
            f"relation_{relation}",
            NODE_TYPES[relation][1],
        ): torch.from_numpy(values.copy())
        for relation, values in edge_confidence.items()
    }

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    device = resolve_device(args.device)
    model_kwargs = {
        "embedding_dim": args.embedding_dim,
        "metapath": METAPATH,
        "walk_length": args.walk_length,
        "context_size": args.context_size,
        "walks_per_node": args.walks_per_node,
        "num_negative_samples": args.negative_samples,
        "num_nodes_dict": {"company": company_count, "person": person_count},
        "sparse": True,
    }
    weighted_sampler = needs_weighted_sampler(
        edge_confidence, args.confidence_mode, args.confidence_alpha
    )
    if not weighted_sampler:
        model = MetaPath2Vec(edge_index_dict, **model_kwargs).to(device)
    else:
        model = ConfidenceMetaPath2Vec(
            edge_index_dict,
            edge_confidence_dict,
            args.confidence_alpha,
            **model_kwargs,
        ).to(device)
    generator = torch.Generator().manual_seed(args.seed)
    loader = model.loader(
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    optimizer = torch.optim.SparseAdam(model.parameters(), lr=args.learning_rate)
    history: list[dict[str, float | int]] = []
    for epoch in range(args.epochs):
        epoch_started = time.time()
        model.train()
        total_loss = 0.0
        batch_count = 0
        for positive_walk, negative_walk in loader:
            optimizer.zero_grad()
            loss = model.loss(positive_walk.to(device), negative_walk.to(device))
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
            batch_count += 1
        mean_loss = total_loss / max(batch_count, 1)
        history.append({"epoch": epoch, "meanLoss": mean_loss})
        print(
            f"epoch={epoch} mean_loss={mean_loss:.6f} "
            f"seconds={time.time() - epoch_started:.3f}",
            flush=True,
        )

    model.eval()
    with torch.no_grad():
        company_embedding = model("company").detach().cpu().numpy()
        person_embedding = model("person").detach().cpu().numpy()
    pd.to_pickle([company_embedding, person_embedding], output_path)
    state = {name: value.detach().cpu() for name, value in model.state_dict().items()}
    torch.save(state, output_dir / "metapath2vec.pt")
    manifest = {
        "protocolVersion": 3,
        "selectionRule": "fixed_unsupervised_epochs_final_state",
        "usesLabels": False,
        "topologyScope": "transductive_train_valid_test_without_labels",
        "graphMode": args.graph_mode,
        "confidenceMode": args.confidence_mode,
        "confidenceAlpha": args.confidence_alpha,
        "positiveSampler": "confidence_weighted" if weighted_sampler else "pyg_uniform",
        "graphSha256": graph_hash,
        "confidenceThreshold": args.confidence_threshold,
        "seed": args.seed,
        "epochs": args.epochs,
        "device": str(device),
        "torchVersion": torch.__version__,
        "cudaVersion": torch.version.cuda,
        "cudaDevice": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "companyCount": company_count,
        "personCount": person_count,
        "edgeCountByRelation": {
            str(relation): len(values) for relation, values in edges.items()
        },
        "hyperparameters": {
            "embeddingDim": args.embedding_dim,
            "walkLength": args.walk_length,
            "contextSize": args.context_size,
            "walksPerNode": args.walks_per_node,
            "negativeSamples": args.negative_samples,
            "batchSize": args.batch_size,
            "learningRate": args.learning_rate,
            "confidenceAlpha": args.confidence_alpha,
        },
        "history": history,
        "runtimeSeconds": time.time() - started,
        "sourceSha256": {
            "originalEmbedding": file_sha256(source_embedding),
            "scenarioManifest": file_sha256(scenario_dir / "manifest.json"),
            "trainer": file_sha256(Path(__file__).resolve()),
            "uncertaintyProtocol": file_sha256(
                Path(__file__).resolve().parent / "protocol.py"
            ),
        },
    }
    manifest["embeddingSha256"] = file_sha256(output_path)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("FINAL_EMBEDDING_JSON=" + json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
