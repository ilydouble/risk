"""Mechanical tensor encoding; concrete adapters choose features and transforms."""

import hashlib
from pathlib import Path

import numpy as np

from riskgnn.dataset_adapters.snapshot_io import load, verified
from riskgnn.dataset_adapters.snapshot_schema import Edge
from riskgnn.workbench.artifacts import seal, write_json


def target_count(config: dict, default: int) -> int:
    if set(config) - {"target_count"}:
        raise ValueError("Unsupported dataset configuration")
    count = config.get("target_count", default)
    if type(count) is not int or not 6 <= count <= 20000:
        raise ValueError("target_count must be an integer between 6 and 20000")
    return count


def prepare(
    validated: Path,
    output: Path,
    protocol: str,
    count: int,
    *,
    log_features: tuple[str, ...] = (),
    standardize: bool = True,
) -> dict:
    manifest, root = verified(validated, protocol)
    snapshots = load(root)
    groups = [
        (split, label, [n for n in data.nodes if n.kind == "company" and n.label == label])
        for split, data in snapshots.items()
        for label in (0, 1)
    ]
    total = sum(len(nodes) for _, _, nodes in groups)
    size = min(count, total)
    quotas = [min(len(nodes), max(1, int(size * len(nodes) / total))) for _, _, nodes in groups]
    # Allocate the exact requested target count without erasing a split/label stratum.
    while sum(quotas) != size:
        delta = 1 if sum(quotas) < size else -1
        for i, (_, _, nodes) in enumerate(groups):
            if (delta > 0 and quotas[i] < len(nodes)) or (delta < 0 and quotas[i] > 1):
                quotas[i] += delta
                if sum(quotas) == size:
                    break
    targets: set[tuple[str, str]] = set()
    for (split, _, nodes), quota in zip(groups, quotas, strict=True):
        ordered = sorted(
            nodes,
            key=lambda n: hashlib.sha256(f"snapshot-subset-v1:{split}:{n.id}".encode()).hexdigest(),
        )
        targets.update((split, n.id) for n in ordered[:quota])
    chosen = set(targets)
    # Preserve direction: only incoming sources can send messages to a target.
    for split, snapshot in snapshots.items():
        incoming: dict[str, list[Edge]] = {}
        for edge in snapshot.edges:
            incoming.setdefault(edge.target, []).append(edge)
        frontier = {node for sp, node in targets if sp == split}
        for _ in range(2):
            neighbors: set[str] = set()
            for node in sorted(frontier):
                ordered_edges = sorted(
                    incoming.get(node, []),
                    key=lambda e: hashlib.sha256(
                        f"{e.source}:{e.target}:{e.relation}".encode()
                    ).hexdigest(),
                )
                neighbors.update(e.source for e in ordered_edges[:4])
            frontier = {node for node in neighbors if (split, node) not in chosen}
            chosen.update((split, node) for node in neighbors)
    records = [
        (split, n) for split, d in snapshots.items() for n in d.nodes if (split, n.id) in chosen
    ]
    records.sort(key=lambda row: (row[1].kind != "company", row[0], row[1].id))
    index = {(split, n.id): i for i, (split, n) in enumerate(records)}
    company_count = sum(n.kind == "company" for _, n in records)
    ids = [n.id if n.kind == "company" else f"@{split}:{n.id}" for split, n in records]
    x = np.array([n.features for _, n in records], dtype=np.float32)
    labels = np.array(
        [n.label if (split, n.id) in targets else -1 for split, n in records], dtype=np.int64
    )
    splits = np.array(
        [
            ("val" if split == "valid" else split) if (split, n.id) in targets else "context"
            for split, n in records
        ]
    )
    train_mask = splits == "train"
    features = snapshots["train"].feature_names
    fill_values, means, scales = [], [], []
    for j, name in enumerate(features):
        if name in log_features:
            if np.any(x[:company_count, j] < 0):
                raise ValueError(f"Negative count feature: {name}")
            x[:, j] = np.log1p(x[:, j])
        available = x[train_mask, j][np.isfinite(x[train_mask, j])]
        fill = float(np.median(available)) if len(available) else 0.0
        x[~np.isfinite(x[:, j]), j] = fill
        mean = float(x[train_mask, j].mean()) if standardize else 0.0
        scale = float(x[train_mask, j].std()) if standardize else 1.0
        scale = scale if scale > 1e-8 else 1.0
        x[:, j] = (x[:, j] - mean) / scale
        fill_values.append(fill)
        means.append(mean)
        scales.append(scale)
    # Persons have a separate embedding projection, never imputed company attributes.
    x[company_count:] = 0
    relations = snapshots["train"].relation_names
    triples, weights, confidence, retained = [], [], [], {}
    for split, snapshot in snapshots.items():
        edges = [
            e for e in snapshot.edges if (split, e.source) in chosen and (split, e.target) in chosen
        ]
        for edge in edges:
            triples.append(
                (
                    index[(split, edge.source)],
                    index[(split, edge.target)],
                    relations.index(edge.relation),
                )
            )
            weights.append(edge.weight)
            confidence.append(
                edge.existence_confidence if edge.existence_confidence is not None else 1
            )
        # Keep unconsumed evidence auditable; membership lists remain snapshot-local.
        retained[split] = {
            "nodes": [n.model_dump() for sp, n in records if sp == split],
            "edges": [e.model_dump(exclude_none=True) for e in edges],
            "hyperedges": [
                {
                    **h.model_dump(exclude_none=True),
                    "sourceMemberCount": len(h.members),
                    "members": [m for m in h.members if (split, m) in chosen],
                    "membership_confidence": [
                        v
                        for m, v in zip(h.members, h.membership_confidence, strict=True)
                        if (split, m) in chosen
                    ]
                    if h.membership_confidence is not None
                    else None,
                }
                for h in snapshot.hyperedges
                if any((split, m) in chosen for m in h.members)
            ],
            "events": [e.model_dump() for e in snapshot.events if (split, e.company) in chosen],
        }
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output / "context.npz",
        features=x,
        labels=labels,
        splits=splits,
        snapshots=np.array([split for split, _ in records]),
        edges=np.array(triples, dtype=np.int64).reshape(-1, 3),
        weights=np.array(weights, dtype=np.float32),
        confidence=np.array(confidence, dtype=np.float32),
    )
    write_json(output / "ids.json", ids)
    write_json(output / "evidence.json", retained)
    metadata = {
        "profile": "snapshot-node-edge-v1",
        "protocol": protocol + "-train-fit-v1",
        "datasetContract": manifest["datasetContract"],
        "datasetFormat": protocol,
        "taskType": "entity_snapshot",
        "target": snapshots["train"].target_description,
        "sourceSha256": manifest["sha256"],
        "seed": 0,
        "targetCount": len(targets),
        "nodeCount": len(records),
        "companyCount": company_count,
        "personCount": len(records) - company_count,
        "edgeCount": len(triples),
        "contextHops": 2,
        "contextFanout": 4,
        "relations": relations,
        "features": features,
        "splitCounts": {name: int(np.sum(splits == name)) for name in ("train", "val", "test")},
        "preprocessing": {
            "fitSplit": "train",
            "log1p": list(log_features),
            "fillValues": fill_values,
            "mean": means,
            "scale": scales,
        },
        "architecture": "dataset-node-edge-v1",
        "edgePolicy": "directed-source-weight-and-explicit-confidence",
        "usedInputs": [
            "company_features",
            "person_embeddings",
            "directed_edges",
            "edge_weight",
            "explicit_edge_confidence",
        ],
        "retainedOnlyInputs": ["hyperedges", "events", "strength", "evidence_metadata"],
        "evaluation": "isolated_snapshots",
    }
    write_json(output / "metadata.json", metadata)
    seal(output, kind="riskgnn-prepared-v1", metadata={"sourceSha256": manifest["sha256"]})
    return metadata
