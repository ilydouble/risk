"""Convert public SMEsD builtin-only pickles into isolated, disjoint snapshots."""

import hashlib
import pickle
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from com_risk_runtime.schema import Dataset

from .data import dump_json

RELATIONS = [
    "supervised",
    "supervise",
    "executed",
    "execute",
    "stakeholderd",
    "stakeholder",
    "invest_CC",
    "invested_CC",
    "invest_CP",
    "invested_CP",
    "branch",
    "branched",
]
FEATURES = ["log_registered_capital", "log_paid_capital", "age_months"]
TARGET = (
    "SMEsD bankruptcy status (1=bankrupt); observation relative to bankruptcy/survival, "
    "not fixed-horizon PD"
)


class BuiltinReader(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"Object construction forbidden: {module}.{name}")


def read(path):
    with open(path, "rb") as stream:
        return BuiltinReader(stream).load()


def convert(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    splits = read(source / "split_data_idx.pkl")
    # Earliest assignment wins; later occurrences are removed completely, including incident edges.
    seen: set[int] = set()
    cleaned: list[set[int]] = []
    for ids in splits:
        selected = set(ids) - seen
        cleaned.append(selected)
        seen.update(ids)
    audit: dict[str, Any] = {
        "source": "https://github.com/shaopengw/ComRisk",
        "source_commit": "a80524b3b67436cd2f74755f6ffa08a554ff2d02",
        "split_policy": "earliest split wins; remove later repeated company nodes and edges",
        "pairwise_overlap": {
            f"{i}-{j}": len(set(splits[i]) & set(splits[j]))
            for i in range(3)
            for j in range(i + 1, 3)
        },
        "meta_embeddings_used": False,
        "snapshots": {},
        "limitations": [
            "Public benchmark, not competition or Southeast Asian data.",
            "Original event ages are outcome-relative, not a uniform forward prediction horizon.",
            "Relation timestamps absent; cannot certify point-in-time compliance.",
            "Group priors use industry categories, not Louvain or country groups.",
        ],
    }
    for k, (split, filename) in enumerate(
        zip(
            ("train", "valid", "test"),
            ("train_data.pkl", "validate_data.pkl", "test_data.pkl"),
            strict=True,
        )
    ):
        risk, attrs, graph, hyper, labels = read(source / filename)
        keep = cleaned[k]
        attributes = {
            idx: (row, label) for idx, row, label in zip(splits[k], attrs, labels, strict=True)
        }
        communities = {idx: name for name, ids in hyper["industry"].items() for idx in ids}
        edges: defaultdict[tuple[int, int, int], float] = defaultdict(float)
        dropped_type = dropped_endpoint = zero_weights = 0
        for (s, t), rel, weight in zip(*graph, strict=True):
            if rel >= 12:
                dropped_type += 1
                continue
            if (s < 3976 and s not in keep) or (t < 3976 and t not in keep):
                dropped_endpoint += 1
                continue
            if weight <= 0:
                zero_weights += 1
                continue
            # Log compression prevents raw capital-size weights dominating attention.
            edges[(s, t, rel)] += float(np.log1p(weight))
        persons = {v for s, t, _ in edges for v in (s, t) if v >= 3976}

        def key(i):
            return f"C{i:05d}" if i < 3976 else f"P{i:05d}"

        nodes = []
        for i in sorted(keep):
            row, label = attributes[i]
            nodes.append(
                {
                    "id": key(i),
                    "features": [float(np.log1p(row[0])), float(np.log1p(row[1])), float(row[2])],
                    "label": label,
                    "split": split,
                    "community": communities.get(i, "unknown"),
                }
            )
        nodes += [{"id": key(i), "kind": "person", "features": [None] * 3} for i in sorted(persons)]
        hyperedges = [
            {"kind": typ, "members": [key(i) for i in sorted(set(ids) & keep)]}
            for typ, groups in hyper.items()
            for ids in groups.values()
            if set(ids) & keep
        ]
        events = [
            {"company": key(i), "cause": e[0], "court": e[1], "result": e[2], "age_months": e[3]}
            for i, records in risk.items()
            if i in keep
            for e in records
        ]
        data = Dataset.model_validate(
            {
                "name": f"SMEsD-disjoint-{split}",
                "synthetic": False,
                "evaluation": "isolated_snapshots",
                "target_description": TARGET,
                "feature_names": FEATURES,
                "relation_names": RELATIONS,
                "hyperedge_types": ["industry", "area", "qualify"],
                "nodes": nodes,
                "edges": [
                    {"source": key(s), "target": key(t), "relation": RELATIONS[r], "weight": w}
                    for (s, t, r), w in edges.items()
                ],
                "hyperedges": hyperedges,
                "events": events,
            }
        )
        data.write(output / f"{split}.json")
        audit["snapshots"][split] = {
            "companies": len(keep),
            "persons": len(persons),
            "edges": len(edges),
            "events": len(events),
            "hyperedges": len(hyperedges),
            "labels": dict(Counter(n["label"] for n in nodes if "label" in n)),
            "removed_duplicate_companies": len(splits[k]) - len(keep),
            "excluded_relation_edges": dropped_type,
            "excluded_endpoint_edges": dropped_endpoint,
            "dropped_nonpositive_edges": zero_weights,
            "sha256": hashlib.sha256((source / filename).read_bytes()).hexdigest(),
        }
    dump_json(output / "audit.json", audit)
    return audit
