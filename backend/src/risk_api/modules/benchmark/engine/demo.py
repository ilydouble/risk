"""Synthetic data for software validation only; never a substitute for MSGraphFin."""

import numpy as np
from sklearn.model_selection import train_test_split

from .data import Dataset


def generate(n=360, seed=42):
    if n < 100:
        raise ValueError("demo needs at least 100 companies")
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 18))
    groups = rng.integers(0, 12, size=n)
    group_effect = rng.normal(size=12)
    logits = 1.3 * x[:, 0] - x[:, 1] + 0.8 * group_effect[groups] - 0.6
    y = rng.binomial(1, 1 / (1 + np.exp(-logits)))
    train_idx, holdout = train_test_split(
        np.arange(n), test_size=0.4, random_state=seed, stratify=y
    )
    valid_idx, test_idx = train_test_split(
        holdout, test_size=0.5, random_state=seed, stratify=y[holdout]
    )
    splits = {
        int(i): s
        for s, ids in [("train", train_idx), ("valid", valid_idx), ("test", test_idx)]
        for i in ids
    }
    nodes = [
        {"id": f"C{i:05d}", "features": row.tolist(), "label": int(y[i]), "split": splits[i]}
        for i, row in enumerate(x)
    ]
    edges = []
    for i in range(n):
        peers = np.flatnonzero(groups == groups[i])
        for j in rng.choice(peers, min(3, len(peers)), replace=False):
            if i != j:
                edges.append(
                    {
                        "source": nodes[int(j)]["id"],
                        "target": nodes[i]["id"],
                        "relation": "equity" if i % 2 else "supply",
                        "weight": float(rng.uniform(0.1, 1)),
                    }
                )
    hyperedges = [
        {"kind": "industry", "members": [nodes[int(i)]["id"] for i in np.flatnonzero(groups == g)]}
        for g in np.unique(groups)
    ]
    return Dataset.model_validate(
        {
            "name": "synthetic-software-demo",
            "synthetic": True,
            "target_description": "Synthetic binary risk outcome; no real-world horizon",
            "feature_names": [f"feature_{i:02d}" for i in range(18)],
            "relation_names": ["equity", "supply"],
            "hyperedge_types": ["industry", "area", "qualification"],
            "nodes": nodes,
            "edges": edges,
            "hyperedges": hyperedges,
        }
    )
