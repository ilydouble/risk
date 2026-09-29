"""Pure data transformations shared by SMEsD uncertainty experiment runners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

VARIANTS: dict[str, dict[str, Any]] = {
    "comrisk_oracle": {
        "use_prior": False,
        "graph": "oracle",
        "confidence": "ignore",
    },
    "comrisk_noisy": {
        "use_prior": False,
        "graph": "all",
        "confidence": "ignore",
    },
    "riskgnn_noisy": {
        "use_prior": True,
        "graph": "all",
        "confidence": "ignore",
    },
    "riskgnn_filter": {
        "use_prior": True,
        "graph": "filter",
        "confidence": "ignore",
    },
    "riskgnn_gated": {
        "use_prior": True,
        "graph": "all",
        "confidence": "gate",
    },
    "riskgnn_shuffled": {
        "use_prior": True,
        "graph": "all",
        "confidence": "shuffle",
    },
    "riskgnn_inverted": {
        "use_prior": True,
        "graph": "all",
        "confidence": "invert",
    },
}

NODE_TYPES = {
    0: ("company", "person"),
    1: ("person", "company"),
    2: ("company", "person"),
    3: ("person", "company"),
    4: ("company", "person"),
    5: ("person", "company"),
    6: ("company", "company"),
    7: ("company", "company"),
    8: ("person", "company"),
    9: ("company", "person"),
    10: ("company", "company"),
    11: ("company", "company"),
}


def embedding_graph_mode(variant: str) -> str:
    """Return the topology used to pretrain the frozen embedding."""
    return str(VARIANTS[variant]["graph"])


def scenario_mask(
    scenario: dict[str, np.ndarray], graph_mode: str, threshold: float
) -> np.ndarray:
    if graph_mode not in {"oracle", "all", "filter"}:
        raise ValueError(f"unknown graph mode {graph_mode}")
    mask = np.ones(len(scenario["source"]), dtype=np.bool_)
    if graph_mode == "oracle":
        mask &= scenario["is_true"]
    elif graph_mode == "filter":
        mask &= scenario["confidence"] >= threshold
    return mask


def build_metapath_edges(
    scenarios: dict[str, dict[str, np.ndarray]],
    graph_mode: str,
    threshold: float,
    company_count: int,
    person_count: int,
) -> dict[int, np.ndarray]:
    """Build deduplicated local-index edge arrays for MetaPath2Vec.

    Scenario files contain one logical direction (the even relation id) in global
    node ids. This function restores the paired reverse relation and converts
    person ids to their local 0-based namespace. It deliberately uses
    ``>= company_count`` at the company/person boundary.
    """
    by_relation: dict[int, list[np.ndarray]] = {relation: [] for relation in range(12)}
    node_count = company_count + person_count
    for scenario in scenarios.values():
        mask = scenario_mask(scenario, graph_mode, threshold)
        source = scenario["source"][mask].astype(np.int64, copy=False)
        target = scenario["target"][mask].astype(np.int64, copy=False)
        relation = scenario["relation"][mask].astype(np.int64, copy=False)
        if ((source < 0) | (source >= node_count)).any() or (
            (target < 0) | (target >= node_count)
        ).any():
            raise ValueError("scenario contains a node id outside the embedding universe")
        for forward in (0, 2, 4, 6, 8, 10):
            relation_mask = relation == forward
            if not relation_mask.any():
                continue
            forward_edges = np.column_stack((source[relation_mask], target[relation_mask]))
            by_relation[forward].append(forward_edges)
            by_relation[forward + 1].append(forward_edges[:, ::-1])

    result: dict[int, np.ndarray] = {}
    for relation, chunks in by_relation.items():
        edges = (
            np.unique(np.concatenate(chunks, axis=0), axis=0)
            if chunks
            else np.empty((0, 2), dtype=np.int64)
        )
        source_type, target_type = NODE_TYPES[relation]
        if source_type == "person":
            if (edges[:, 0] < company_count).any():
                raise ValueError(f"relation {relation} has a company in person source slot")
            edges[:, 0] -= company_count
        elif (edges[:, 0] >= company_count).any():
            raise ValueError(f"relation {relation} has a person in company source slot")
        if target_type == "person":
            if (edges[:, 1] < company_count).any():
                raise ValueError(f"relation {relation} has a company in person target slot")
            edges[:, 1] -= company_count
        elif (edges[:, 1] >= company_count).any():
            raise ValueError(f"relation {relation} has a person in company target slot")
        result[relation] = edges
    return result


def load_scenario(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        scenario = {name: archive[name] for name in archive.files}
    required = {"source", "target", "relation", "strength", "confidence", "is_true"}
    if set(scenario) != required:
        raise ValueError(f"scenario keys differ: expected {sorted(required)}")
    size = len(scenario["source"])
    if any(len(values) != size for values in scenario.values()):
        raise ValueError("scenario arrays have different lengths")
    if not np.isin(scenario["relation"], [0, 2, 4, 6, 8, 10]).all():
        raise ValueError("scenario contains unsupported relation types")
    if not ((scenario["confidence"] >= 0) & (scenario["confidence"] <= 1)).all():
        raise ValueError("confidence must be within [0, 1]")
    return scenario


def _shuffle_confidence_within_relation(
    confidence: np.ndarray, relation: np.ndarray, seed: int
) -> np.ndarray:
    shuffled = confidence.copy()
    rng = np.random.default_rng(seed + 917_531)
    for relation_type in sorted({int(value) for value in relation}):
        indices = np.flatnonzero(relation == relation_type)
        shuffled[indices] = confidence[rng.permutation(indices)]
    return shuffled


def build_directed_graph(
    scenario: dict[str, np.ndarray], variant: str, seed: int, threshold: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    config = VARIANTS[variant]
    mask = np.ones(len(scenario["source"]), dtype=np.bool_)
    if config["graph"] == "oracle":
        mask &= scenario["is_true"]
    elif config["graph"] == "filter":
        mask &= scenario["confidence"] >= threshold

    source = scenario["source"][mask].astype(np.int64, copy=False)
    target = scenario["target"][mask].astype(np.int64, copy=False)
    relation = scenario["relation"][mask].astype(np.int64, copy=False)
    strength = scenario["strength"][mask].astype(np.float32, copy=False)
    confidence = scenario["confidence"][mask].astype(np.float32, copy=True)

    # Canonical ordering makes the clean oracle bitwise identical across noise
    # scenarios and removes candidate-file row order as an experimental factor.
    order = np.lexsort((target, source, relation))
    source = source[order]
    target = target[order]
    relation = relation[order]
    strength = strength[order]
    confidence = confidence[order]

    confidence_mode = config["confidence"]
    if confidence_mode == "ignore":
        confidence.fill(1.0)
    elif confidence_mode == "shuffle":
        confidence = _shuffle_confidence_within_relation(confidence, relation, seed)
    elif confidence_mode == "invert":
        confidence = np.clip(1.05 - confidence, 0.05, 1.0).astype(np.float32)
    elif confidence_mode != "gate":
        raise ValueError(f"unknown confidence mode {confidence_mode}")

    edge_index = np.column_stack(
        (np.concatenate((source, target)), np.concatenate((target, source)))
    )
    edge_type = np.concatenate((relation, relation + 1))
    edge_strength = np.concatenate((strength, strength))
    edge_confidence = np.concatenate((confidence, confidence))
    return edge_index, edge_type, edge_strength, edge_confidence
