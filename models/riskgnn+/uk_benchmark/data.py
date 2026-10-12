"""Load the UK Companies House / GLEIF benchmark for the riskgnn+ comparison.

The input is the ``com_risk_runtime.schema.Dataset`` v1 triple in
``datasets/uk_dataset_v1`` (``train.json`` / ``valid.json`` / ``test.json``).
The three snapshots are isolated: they share no company ID, so the loader builds a
single transductive node universe by concatenating them in file order.

Notable differences from SMEsD, all absorbed here:

* 7 company features instead of 3; 4 relation types instead of 12.
* No person nodes and no court events (``risk_data`` stays empty).
* No pretrained metapath2vec embedding. Node representations start from the same
  frozen random projection (``Normal(0, 0.1)``) the workbench uses for datasets
  without an upstream embedding; ``com_emb`` is shared across the three models.
* ``SAME_ADDRESS`` edges carry evidence weights in ``[0.3, 1.0]``; the other three
  relations are exactly ``1.0``. The reference protocol keeps them; ``--edge-weights
  uniform`` reruns with all weights forced to 1.0.

Preprocessing follows the approved adapter protocol
(``uk-dataset-v1-train-fit-v1``): log1p on every count column (all but
``age_months``), then median imputation and z-scoring with statistics fit on the
training target only. The loader never reads or writes ``audit.json``.

This module deliberately imports only numpy so the contract can be tested without
torch. Incidence tensors are built by :mod:`uk_benchmark.training`.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path

import numpy as np

SPLIT_FILES = (
    ("train", "train.json"),
    ("valid", "valid.json"),
    ("test", "test.json"),
)
SPLIT_ORDER = ("train", "valid", "cal", "test")
SNAPSHOT_OF = {"train": "train", "valid": "valid", "cal": "valid", "test": "test"}


def _stratified_positions(
    labels: np.ndarray, cap: int | None, rng: np.random.Generator
) -> np.ndarray:
    """Pick at most ``cap`` node positions, preserving the label ratio.

    Used only for smoke tests; ``cap=None`` returns every position untouched.
    """
    if cap is None or cap >= len(labels):
        return np.arange(len(labels), dtype=np.int64)
    positions = []
    for value in (0, 1):
        pool = np.flatnonzero(labels == value)
        take = min(int(round(cap * len(pool) / len(labels))), len(pool))
        if take:
            positions.append(rng.choice(pool, size=take, replace=False))
    if not positions:
        return np.array([], dtype=np.int64)
    return np.sort(np.concatenate(positions))


def _index_nodes(snapshot: dict) -> np.ndarray:
    labels = np.asarray([node["label"] for node in snapshot["nodes"]], dtype=np.int64)
    return labels


def load_uk_benchmark(
    data_dir: Path,
    *,
    embed_dim: int = 32,
    embed_seed: int = 0,
    standardize: bool = True,
    calib_fraction: float = 0.5,
    calib_seed: int = 42,
    max_nodes: int | None = None,
    uniform_weights: bool = False,
) -> dict:
    """Read the UK snapshots into the structure the training module consumes.

    ``max_nodes`` exists for smoke runs: it caps each snapshot with a stratified
    sample and filters edges/hyperedges to the surviving nodes. ``uniform_weights``
    ignores the source ``weight`` field and sets every edge weight to 1.0.
    """
    data_dir = Path(data_dir)
    if not 0.0 < calib_fraction < 1.0:
        raise ValueError("calib_fraction must be in (0, 1)")

    payloads = {}
    source_sha256 = {}
    for name, filename in SPLIT_FILES:
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing UK snapshot: {path}")
        payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        source_sha256[filename] = hashlib.sha256(path.read_bytes()).hexdigest()

    base = payloads["train"]
    feature_names = list(base["feature_names"])
    relation_names = list(base["relation_names"])
    hyperedge_kinds = list(base.get("hyperedge_types") or [])
    for name, payload in payloads.items():
        if list(payload["feature_names"]) != feature_names:
            raise ValueError(f"{name} feature_names differ from train")
        if list(payload["relation_names"]) != relation_names:
            raise ValueError(f"{name} relation_names differ from train")
        if payload.get("events"):
            raise ValueError(f"{name} carries court events; the UK loader expects []")

    # Global node universe: snapshots in fixed order, nodes in file order.
    rng = np.random.default_rng(embed_seed)
    positions: dict[str, np.ndarray] = {}
    local_to_global: dict[str, dict[int, int]] = {}
    node_ids: list[str] = []
    offsets: dict[str, int] = {}
    for name, _ in SPLIT_FILES:
        nodes = payloads[name]["nodes"]
        chosen = _stratified_positions(_index_nodes(payloads[name]), max_nodes, rng)
        positions[name] = chosen
        offsets[name] = len(node_ids)
        local_to_global[name] = {
            int(pos): offsets[name] + rank for rank, pos in enumerate(chosen)
        }
        node_ids.extend(nodes[int(pos)]["id"] for pos in chosen)
    company_num = len(node_ids)

    # Raw features / labels / community, scattered to global indices.
    raw = np.zeros((company_num, len(feature_names)), dtype=np.float32)
    labels = np.zeros(company_num, dtype=np.int64)
    community = np.empty(company_num, dtype=object)
    snapshot_of = np.empty(company_num, dtype=object)
    for name, _ in SPLIT_FILES:
        nodes = payloads[name]["nodes"]
        for local, global_idx in local_to_global[name].items():
            node = nodes[local]
            raw[global_idx] = np.asarray(node["features"], dtype=np.float32)
            labels[global_idx] = int(node["label"])
            community[global_idx] = str(node.get("community", "未知"))
            snapshot_of[global_idx] = name

    train_mask = np.asarray([value == "train" for value in snapshot_of])
    log_features = tuple(name for name in feature_names if name != "age_months")
    features = raw.copy()
    for column_idx, name in enumerate(feature_names):
        column = features[:, column_idx]
        if name in log_features:
            if np.any(column < 0):
                raise ValueError(f"negative count feature: {name}")
            column = np.log1p(column)
        finite_train = column[train_mask][np.isfinite(column[train_mask])]
        fill = float(np.median(finite_train)) if len(finite_train) else 0.0
        column = np.where(np.isfinite(column), column, fill)
        if standardize:
            train_values = column[train_mask]
            mean = float(train_values.mean()) if len(train_values) else 0.0
            scale = float(train_values.std()) if len(train_values) else 1.0
            scale = scale if scale > 1e-8 else 1.0
            column = (column - mean) / scale
        features[:, column_idx] = column

    # Graphs and hyperedges per snapshot, restricted to the surviving nodes.
    graphs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    hyper_map: dict[str, dict[str, OrderedDict]] = {}
    for name, _ in SPLIT_FILES:
        nodes = payloads[name]["nodes"]
        mapping = local_to_global[name]
        index_of_id = {node["id"]: local for local, node in enumerate(nodes)}

        pairs, types, weights = [], [], []
        for edge in payloads[name]["edges"]:
            source = mapping.get(index_of_id.get(edge["source"], -1))
            target = mapping.get(index_of_id.get(edge["target"], -1))
            if source is None or target is None:
                continue
            pairs.append((source, target))
            types.append(relation_names.index(edge["relation"]))
            weights.append(1.0 if uniform_weights else float(edge.get("weight", 1.0)))
        graphs[name] = (
            np.asarray(pairs, dtype=np.int64).reshape(-1, 2),
            np.asarray(types, dtype=np.int64),
            np.asarray(weights, dtype=np.float32),
        )

        groups: dict[str, OrderedDict] = {kind: OrderedDict() for kind in hyperedge_kinds}
        for hyperedge_idx, hyperedge in enumerate(payloads[name]["hyperedges"]):
            kind = hyperedge["kind"]
            bucket = groups.setdefault(kind, OrderedDict())
            members = {
                mapping[int(index_of_id[member])]
                for member in hyperedge["members"]
                if member in index_of_id and int(index_of_id[member]) in mapping
            }
            if len(members) >= 2:
                bucket[f"{kind}:{hyperedge_idx}"] = sorted(members)
        hyper_map[name] = groups

    # Split indices; validation is halved into model-selection and calibration, as
    # in run_smesd_experiments.py (same RandomState permutation convention).
    split_index = {
        name: np.flatnonzero(np.asarray(snapshot_of) == name) for name in ("train", "valid", "test")
    }
    valid_idx = split_index["valid"]
    permutation = np.random.RandomState(calib_seed).permutation(len(valid_idx))
    n_cal = int(round(len(valid_idx) * calib_fraction))
    split_index["cal"] = valid_idx[permutation[:n_cal]]
    split_index["valid"] = valid_idx[permutation[n_cal:]]

    splits = {}
    for name in SPLIT_ORDER:
        idx = np.asarray(split_index[name], dtype=np.int64)
        snapshot_name = SNAPSHOT_OF[name]
        splits[name] = {
            "idx": idx,
            "attr": features[idx],
            "y": labels[idx],
            "community": [str(community[int(i)]) for i in idx],
            "graph": graphs[snapshot_name],
            "snapshot": snapshot_name,
            "risk": {},
        }

    hypergraphs = {
        name: [
            hyper_map[SNAPSHOT_OF[name]].get(kind, OrderedDict())
            for kind in hyperedge_kinds
        ]
        for name in SPLIT_ORDER
    }

    com_emb = np.random.RandomState(embed_seed).normal(
        0.0, 0.1, size=(company_num, embed_dim)
    ).astype(np.float32)
    return {
        "name": "uk-dataset-v1",
        "feature_names": feature_names,
        "relation_names": relation_names,
        "hyperedge_kinds": hyperedge_kinds,
        "log_features": log_features,
        "company_num": company_num,
        "person_num": 0,
        "com_emb": com_emb,
        "per_emb": np.zeros((0, embed_dim), dtype=np.float32),
        "node_ids": node_ids,
        "splits": splits,
        "hypergraphs": hypergraphs,
        "uniform_weights": uniform_weights,
        "max_nodes": max_nodes,
        "source_sha256": source_sha256,
    }


def summarize(dataset: dict) -> dict:
    """Compact description for the run manifest and logs."""
    return {
        "name": dataset["name"],
        "company_num": dataset["company_num"],
        "features": dataset["feature_names"],
        "relations": dataset["relation_names"],
        "hyperedge_kinds": dataset["hyperedge_kinds"],
        "uniform_weights": dataset["uniform_weights"],
        "max_nodes": dataset["max_nodes"],
        "split_sizes": {name: int(len(split["y"])) for name, split in dataset["splits"].items()},
        "positive_rate": {
            name: float(np.mean(split["y"])) if len(split["y"]) else 0.0
            for name, split in dataset["splits"].items()
        },
        "edge_counts": {
            name: int(split["graph"][0].shape[0]) for name, split in dataset["splits"].items()
        },
    }
