"""Apply persisted training statistics without fitting to inference data."""

import numpy as np
import torch

from .schema import Dataset


def tensorize(data: Dataset, preprocessor: dict) -> dict:
    index = {n.id: i for i, n in enumerate(data.nodes)}
    raw = np.array([n.features for n in data.nodes], dtype=float)
    clean = np.where(np.isnan(raw), preprocessor["median"], raw)
    values = np.clip((clean - preprocessor["mean"]) / preprocessor["std"], -10, 10)
    # Missingness remains observable after median imputation.
    x = torch.tensor(np.concatenate([values, np.isnan(raw)], axis=1), dtype=torch.float32)
    relations = []
    for name in data.relation_names:
        edges = [e for e in data.edges if e.relation == name]
        relations.append(
            (
                torch.tensor([index[e.source] for e in edges], dtype=torch.long),
                torch.tensor([index[e.target] for e in edges], dtype=torch.long),
                torch.tensor([e.weight for e in edges], dtype=torch.float32),
            )
        )
    incidence = []
    for name in data.hyperedge_types:
        groups = [h for h in data.hyperedges if h.kind == name]
        pairs = [(index[n], j) for j, h in enumerate(groups) for n in h.members]
        incidence.append(
            (
                torch.tensor([p[0] for p in pairs], dtype=torch.long),
                torch.tensor([p[1] for p in pairs], dtype=torch.long),
                len(groups),
            )
        )
    events = torch.tensor(
        [[index[e.company], e.cause, e.court, e.result, e.age_months] for e in data.events],
        dtype=torch.float32,
    ).reshape(-1, 5)
    return {
        "x": x,
        "kinds": torch.tensor([n.kind == "person" for n in data.nodes], dtype=torch.long),
        "relations": relations,
        "incidence": incidence,
        "events": events,
        "y": torch.tensor(
            [n.label if n.label is not None else -1 for n in data.nodes], dtype=torch.float32
        ),
        "masks": {
            s: torch.tensor([n.split == s for n in data.nodes]) for s in ("train", "valid", "test")
        },
    }
