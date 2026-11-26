"""Model-ready company graphs for the three research Data Packages."""

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from riskgnn.dataset_adapters.archive import unpack
from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult
from riskgnn.dataset_adapters.delivery import delivery_for
from riskgnn.dataset_adapters.enterprise import attributes
from riskgnn.dataset_adapters.snapshot_io import verified
from riskgnn.dataset_adapters.standard.contract import check_resources
from riskgnn.workbench.artifacts import digest, read_json, seal, write_json

SPLITS = ("train", "val", "test")
POLICIES = {
    "hat": ("deduplicated", "Published company bankruptcy label"),
    "figraph": ("jev-frozen", "Same-year listed company financial anomaly"),
    "msgraphfin": ("published", "Published TRUE/FALSE risk status"),
}
MAX_ROWS = 400_000
STANDARDIZED_LIMIT = 12.0


@dataclass
class ResearchGraph:
    ids: list[str]
    features: list[str]
    x: np.ndarray
    labels: np.ndarray
    splits: np.ndarray
    relations: list[str]
    edges: list[tuple[str, str, str, float]]
    groups: list[tuple[str, list[str]]]


def rows(root: Path, name: str, fields: list[str]):
    source = pq.ParquetFile(root / (name + ".parquet"))
    if source.metadata.num_rows > MAX_ROWS:
        raise ValueError(f"Too many rows in research table {name}")
    return source.read(columns=fields).to_pylist()


def assign_labels(root: Path, ids: list[str], protocol: str) -> tuple[np.ndarray, np.ndarray]:
    indexed = {}
    for row in rows(root, "labels", ["sample_id", "label"]):
        sample, label = row["sample_id"], row["label"]
        if sample in indexed or type(label) is not int or label not in (0, 1):
            raise ValueError("Invalid research label or duplicate sample")
        indexed[sample] = label
    if set(indexed) != set(ids):
        raise ValueError("Research observations and labels must share the same sample IDs")
    lookup = {}
    for row in rows(root, "splits", ["protocol", "split", "sample_id"]):
        if row["protocol"] != protocol:
            continue
        sample = row["sample_id"]
        split = "val" if row["split"] == "valid" else row["split"]
        if split not in SPLITS or sample not in indexed or sample in lookup:
            raise ValueError("Unknown or overlapping research split")
        lookup[sample] = split
    labels = np.array([indexed[sample] if sample in lookup else -1 for sample in ids])
    splits = np.array([lookup.get(sample, "context") for sample in ids])
    if any(set(labels[splits == split]) != {0, 1} for split in SPLITS):
        raise ValueError("Each frozen research split requires both labels")
    return labels, splits


def graph_rows(root: Path, dataset: str, ids: set[str]):
    if dataset == "hat":
        relations = ["CIC", "CC", "CMC"]
        edges = [
            (row["source"], row["target"], kind, float(row["weight"]))
            for kind in relations
            for row in rows(root, f"csr_{kind.lower()}", ["source", "target", "weight"])
            if row["source"] != row["target"]
        ]
        if any(
            a not in ids or b not in ids or not np.isfinite(w) or w <= 0 for a, b, _, w in edges
        ):
            raise ValueError("Invalid HAT CSR edge")
        return relations, edges, []

    raw = rows(root, "edges", ["source", "target", "relation", "graph_view"])
    if dataset == "msgraphfin":
        edges = [
            (row["source"], row["target"], f"{row['graph_view']}:{row['relation']}", 1.0)
            for row in raw
            if row["graph_view"] in {"investrelation", "supplychain"}
        ]
        if len(edges) != len(raw) or any(a not in ids or b not in ids for a, b, _, _ in edges):
            raise ValueError("Invalid MSGraphFin investment or supply edge")
        return sorted({kind for _, _, kind, _ in edges}), edges, []

    entities = {row["entity_id"] for row in rows(root, "entities", ["entity_id"])}
    if not ids.issubset(entities):
        raise ValueError("Missing FiGraph company entity")
    edges, anchors, kinds = set(), defaultdict(set), set()
    for row in raw:
        a, b, kind = row["source"], row["target"], row["relation"]
        if a not in entities or b not in entities or not kind:
            raise ValueError("Invalid FiGraph edge")
        kinds.add(kind)
        if a in ids and b in ids and a != b:
            edges.update(((a, b, kind, 1.0), (b, a, kind, 1.0)))
        elif (a in ids) != (b in ids):
            company, anchor = (a, b) if a in ids else (b, a)
            anchors[kind, anchor].add(company)
    groups = [
        (kind, sorted(members))
        for (kind, _), members in sorted(anchors.items())
        if len(members) >= 2
    ]
    return sorted(kinds), sorted(edges), groups


def load_graph(root: Path, dataset: str) -> ResearchGraph:
    task = read_json(root / "task.json")
    names = task["featureNames"]
    if not isinstance(names, list) or not 0 < len(names) <= 800 or len(set(names)) != len(names):
        raise ValueError("Invalid research feature dictionary")
    if dataset == "figraph":
        names = [name for name in names if name != "IndustryCodeC"]
        allowed = set(pq.read_schema(root / "observations.parquet").names) - {
            "sample_id",
            "company_id",
            "observation_year",
            "label",
            "split",
            "IndustryCodeC",
        }
        if not names or set(names) != allowed:
            raise ValueError("Feature dictionary must match FiGraph numeric source columns")
        observations = rows(root, "observations", ["sample_id", *names])
        values = [[row[name] for name in names] for row in observations]
    else:
        width = 89 if dataset == "hat" else 18
        if names != [f"F{i}" for i in range(width)]:
            raise ValueError("Research vector feature dictionary changed")
        observations = rows(root, "observations", ["sample_id", "features"])
        values = [row["features"] for row in observations]
    ids = [row["sample_id"] for row in observations]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Invalid research observation identity")
    x = np.asarray(values, dtype=np.float32)
    if x.shape != (len(ids), len(names)):
        raise ValueError("Research feature matrix does not match its dictionary")
    labels, splits = assign_labels(root, ids, POLICIES[dataset][0])
    relations, edges, groups = graph_rows(root, dataset, set(ids))
    if not relations:
        raise ValueError("Research graph has no relation types")
    return ResearchGraph(ids, names, x, labels, splits, relations, edges, groups)


def selected_targets(graph: ResearchGraph, count: int) -> np.ndarray:
    groups = [
        np.flatnonzero((graph.splits == split) & (graph.labels == label))
        for split in SPLITS
        for label in (0, 1)
    ]
    size = min(count, sum(map(len, groups)))
    total = sum(map(len, groups))
    allocations = [min(len(group), max(1, size * len(group) // total)) for group in groups]
    while sum(allocations) != size:
        delta = 1 if sum(allocations) < size else -1
        for index, group in enumerate(groups):
            quota = allocations[index] + delta
            if 1 <= quota <= len(group):
                allocations[index] = quota
                if sum(allocations) == size:
                    break
    keep = np.zeros(len(graph.ids), dtype=bool)
    for group, quota in zip(groups, allocations, strict=True):
        ranked = sorted(group, key=lambda i: hashlib.sha256(graph.ids[i].encode()).digest())
        keep[ranked[:quota]] = True
    return keep


class ResearchPackageAdapter(DatasetAdapter):
    id = "research-parquet"
    version = "1"
    trainable = True

    def __init__(self, dataset: str, descriptor: dict):
        self.dataset, self.descriptor = dataset, descriptor
        self.protocol = f"{dataset}-datapackage-v1"

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        delivery = delivery_for(self.id, self.version)
        delivery.config(config)
        files = unpack(archive, workspace)
        check_resources(self.descriptor, files)
        delivery.check_files(workspace)
        graph = load_graph(workspace, self.dataset)
        splits = [
            {
                "split": split,
                "count": int((graph.splits == split).sum()),
                "positives": int(((graph.splits == split) & (graph.labels == 1)).sum()),
            }
            for split in SPLITS
        ]
        return InspectionResult.model_validate(
            {
                "protocol": self.protocol,
                "root": ".",
                "sha256": digest(archive),
                "files": files,
                "counts": {
                    "company_attr": len(graph.ids),
                    "edges": len(graph.edges),
                    "hyperedges": len(graph.groups),
                },
                "features": graph.features,
                "labeledCount": int((graph.labels >= 0).sum()),
                "positiveCount": int((graph.labels == 1).sum()),
                "datasetProfile": {
                    "datasetFormat": self.protocol,
                    "taskType": "entity_snapshot",
                    "target": POLICIES[self.dataset][1],
                    "evaluation": "static_transductive",
                },
                "splits": splits,
                "limitations": [
                    "Original frozen target split; the static graph shares unsupervised context",
                    "No point-in-time claim",
                ],
                "metadata": {
                    "inputFormat": "data-package-2.0",
                    "splitProtocol": POLICIES[self.dataset][0],
                },
            }
        )

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        manifest, root = verified(validated, self.protocol)
        graph = load_graph(root, self.dataset)
        count = delivery_for(self.id, self.version).config(config)["target_count"]
        keep = selected_targets(graph, count)
        labels = np.where(keep, graph.labels, -1)
        splits = np.where(keep, graph.splits, "context")
        train = splits == "train"
        fill, means, scales = [], [], []
        for col in graph.x.T:
            observed = col[train & np.isfinite(col)]
            value = float(np.median(observed)) if len(observed) else 0.0
            col[~np.isfinite(col)] = value
            mean = float(col[train].mean(dtype=np.float64))
            scale = float(col[train].std(dtype=np.float64))
            scale = scale if scale > 1e-8 else 1.0
            # A rare or near-constant train feature can otherwise dominate a shared graph.
            col[:] = np.clip(
                (col.astype(np.float64) - mean) / scale, -STANDARDIZED_LIMIT, STANDARDIZED_LIMIT
            )
            fill.append(value)
            means.append(mean)
            scales.append(scale)
        index = {name: i for i, name in enumerate(graph.ids)}
        types = {name: i for i, name in enumerate(graph.relations)}
        triples = [(index[a], index[b], types[k]) for a, b, k, _ in graph.edges]
        output.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            output / "context.npz",
            features=graph.x,
            labels=labels,
            splits=splits,
            snapshots=np.full(len(index), "static"),
            edges=np.asarray(triples, dtype=np.int64).reshape(-1, 3),
            weights=np.array([w for _, _, _, w in graph.edges], dtype=np.float32),
        )
        write_json(output / "ids.json", graph.ids)
        write_json(
            output / "evidence.json",
            {
                "static": {
                    "hyperedges": [{"kind": k, "members": members} for k, members in graph.groups],
                    "events": [],
                }
            },
        )
        meta = {
            "profile": "research-static-graph-v1",
            "protocol": self.protocol + "-train-fit-v1",
            "datasetFormat": self.protocol,
            "datasetContract": manifest["datasetContract"],
            "sourceSha256": manifest["sha256"],
            "taskType": "entity_snapshot",
            "target": POLICIES[self.dataset][1],
            "seed": 0,
            "targetCount": int(keep.sum()),
            "nodeCount": len(index),
            "companyCount": len(index),
            "personCount": 0,
            "edgeCount": len(triples),
            "relations": graph.relations,
            "features": graph.features,
            "splitCounts": {split: int((splits == split).sum()) for split in SPLITS},
            "preprocessing": {
                "fitSplit": "train",
                "fillValues": fill,
                "mean": means,
                "scale": scales,
                "clipSigma": STANDARDIZED_LIMIT,
            },
            "evaluation": "static_transductive",
            "hyperedgeTypes": sorted({kind for kind, _ in graph.groups}),
            "edgePolicy": "research-static-graph",
            "retainedOnlyInputs": {
                "hat": ["raw_edges", "person_attributes", "published_split", "audit_before2019"],
                "figraph": ["source_background_entities", "IndustryCodeC"],
                "msgraphfin": ["source_groups", "performance_status_audit"],
            }[self.dataset],
        }
        write_json(output / "metadata.json", meta)
        seal(output, kind="riskgnn-prepared-v1", metadata={"sourceSha256": manifest["sha256"]})
        return meta

    def enterprise_records(self, validated: Path):
        _, root = verified(validated, self.protocol)
        graph = load_graph(root, self.dataset)
        for i, name in enumerate(graph.ids):
            label, split = int(graph.labels[i]), str(graph.splits[i])
            yield EnterpriseRecord.model_validate(
                {
                    "kind": "company",
                    "snapshot": "static",
                    "nodeId": name,
                    "data": {
                        "attributes": attributes(graph.features, graph.x[i]),
                        "label": label if label >= 0 else None,
                        "split": split if split != "context" else None,
                    },
                }
            )
        for a, b, kind, weight in graph.edges:
            yield EnterpriseRecord.model_validate(
                {
                    "kind": "edge",
                    "snapshot": "static",
                    "source": a,
                    "target": b,
                    "data": {"relation": kind, "weight": weight},
                }
            )
        for kind, members in graph.groups:
            yield EnterpriseRecord.model_validate(
                {
                    "kind": "hyperedge",
                    "snapshot": "static",
                    "members": members,
                    "data": {"kind": kind, "is_inferred": True},
                }
            )
