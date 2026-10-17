"""Encode retained hyperedges/events without changing the adapter's split policy."""

from pathlib import Path

import numpy as np

from riskgnn.dataset_adapters.acra.paths import data_root
from riskgnn.dataset_adapters.acra.validation import connect
from riskgnn.dataset_adapters.snapshot_io import verified
from riskgnn.workbench.artifacts import read_json, seal, verify, write_json

FORMAT = "riskgnn-plus-model-v1"
ARCHITECTURE = "riskgnn-plus-hyper-v1"


def prepare(adapter, validated: Path, output: Path, config: dict) -> dict:
    adapter.prepare(validated, output, config)
    verify(output, "riskgnn-prepared-v1")
    meta = read_json(output / "metadata.json")
    ids = read_json(output / "ids.json")
    context = dict(np.load(output / "context.npz", allow_pickle=False))
    company_count = meta.get("companyCount", len(ids))
    # UK full snapshots contain 233,251 companies and 789,487 memberships.
    node_limit = 300_000 if adapter.id == "uk-dataset-v1" else 100_000
    incidence_limit = 2_000_000 if adapter.id == "uk-dataset-v1" else 500_000
    if len(ids) > node_limit:
        raise ValueError(
            f"RiskGNN+ prepared graph exceeds {node_limit:,} nodes; reduce target_count"
        )
    index = {name: i for i, name in enumerate(ids[:company_count])}
    if "snapshots" not in context:
        context["snapshots"] = np.full(len(ids), "static")
    groups: list[list[list[int]]] = []
    events: dict[str, list] = {}
    if (output / "evidence.json").is_file():
        evidence = read_json(output / "evidence.json")
        _, root = verified(validated, meta["datasetFormat"])
        # Type ordering belongs to the validated snapshot schema, not alphabetical guesses.
        names = read_json(root / "train.json")["hyperedge_types"]
        groups = [[] for _ in names]
        for snapshot in evidence.values():
            for group in snapshot["hyperedges"]:
                members = [index[name] for name in group["members"]]
                if len(members) >= 2:
                    groups[names.index(group["kind"])].append(members)
            for event in snapshot["events"]:
                events.setdefault(str(index[event["company"]]), []).append(
                    [
                        event["cause"],
                        event["court"],
                        event["result"],
                        event["age_months"],
                    ]
                )
    else:
        names = ["industry", "area", "qualify"]
        groups = [[] for _ in names]
        # Optional ACRA membership files have a declared, historical source schema.
        with connect(data_root(validated)) as db:
            for i, name in enumerate(names):
                path = data_root(validated) / f"hypergraph_{name}.parquet"
                if not path.is_file():
                    continue
                rows = db.read_parquet(str(path))
                if not {"company_id", "group_value"}.issubset(rows.columns):
                    raise ValueError(f"Invalid ACRA hypergraph membership schema: {name}")
                selected: dict[str, list[int]] = {}
                cursor = rows.project("company_id,group_value").execute()
                while batch := cursor.fetchmany(2000):
                    for company, group in batch:
                        if company in index and group is not None:
                            selected.setdefault(str(group), []).append(index[company])
                groups[i] = [sorted(set(members)) for members in selected.values()]
    incidence_count = 0
    for i, typed in enumerate(groups):
        node, group = [], []
        for number, members in enumerate(typed):
            node.extend(members)
            group.extend([number] * len(members))
        context[f"hyper_nodes_{i}"] = np.array(node, dtype=np.int64)
        context[f"hyper_groups_{i}"] = np.array(group, dtype=np.int64)
        context[f"hyper_count_{i}"] = np.array(len(typed), dtype=np.int64)
        incidence_count += len(node)
    if incidence_count > incidence_limit:
        raise ValueError("RiskGNN+ prepared incidence limit exceeded; reduce target_count")
    context["company_embedding"] = np.random.RandomState(0).normal(0, 0.1, (company_count, 32))
    context["person_embedding"] = np.random.RandomState(1).normal(
        0, 0.1, (len(ids) - company_count, 32)
    )
    np.savez_compressed(output / "context.npz", **context)
    write_json(output / "risk_events.json", events)
    retained = set(meta.get("retainedOnlyInputs", [])) - {"hyperedges", "events"}
    if adapter.id == "sg-comrisk":
        retained.add("risk_data_attachment")
    meta.update(
        {
            "algorithm": "RiskGNN+",
            "architecture": ARCHITECTURE,
            "companyCount": company_count,
            "personCount": len(ids) - company_count,
            "hyperedgeTypes": names,
            "hyperedgeCount": sum(map(len, groups)),
            "incidenceCount": incidence_count,
            "eventCount": sum(map(len, events.values())),
            "profile": "riskgnn-plus-induced-subgraph-v1",
            "hypergraphPolicy": "unit-weight-induced-membership-within-snapshot",
            "embeddingSource": "deterministic-workbench-initialization",
            "usedInputs": ["company_features", "directed_edges", "edge_weight"]
            + (["person_embeddings"] if len(ids) > company_count else [])
            + (["hyperedges"] if incidence_count else [])
            + (["risk_events"] if events else []),
            "retainedOnlyInputs": sorted(
                retained
                | {
                    "hyperedge_confidence",
                    "membership_confidence",
                    "evidence_metadata",
                }
            ),
        }
    )
    # The original ACRA prepared graph is bidirectional/unit-weight; preserve that policy.
    # RiskGNN+ learns evidence rather than consuming externally supplied edge confidence.
    meta["retainedOnlyInputs"].append("explicit_edge_confidence")
    meta["edgePolicy"] = (
        "bidirectional-unit-weights"
        if adapter.id == "sg-comrisk"
        else "directed-source-weight-only"
    )
    write_json(output / "metadata.json", meta)
    seal(output, kind="riskgnn-prepared-v1", metadata={"sourceSha256": meta["sourceSha256"]})
    return meta
