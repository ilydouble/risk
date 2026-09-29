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
