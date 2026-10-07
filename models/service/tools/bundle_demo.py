from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast


def _csv_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build_demo_bundle(
    output: str | Path,
    task_type: Literal["loan_application", "entity_snapshot"] = "loan_application",
    *,
    rows: int = 180,
    seed: int = 42,
    include_graph: bool = False,
) -> Path:
    """Create a deterministic Bundle v1 used by local acceptance tests and demos."""
    if rows < 60:
        raise ValueError("demo bundle requires at least 60 samples")
    rng = random.Random(seed)
    samples: list[dict[str, object]] = []
    for index in range(rows):
        split = "train" if index < rows * 0.6 else "validation" if index < rows * 0.8 else "test"
        debt_ratio = round(rng.uniform(0.05, 0.95), 5)
        overdue_count = rng.randrange(0, 5)
        years = rng.randrange(1, 25)
        probability = 0.08 + 0.5 * debt_ratio + 0.08 * overdue_count - 0.015 * years
        target = int(rng.random() < max(0.02, min(0.9, probability)))
        samples.append(
            {
                "sample_id": f"S{index:05d}",
                "entity_id": f"C{index % 72:04d}",
                "observation_time": f"2025-{index % 12 + 1:02d}-01T00:00:00Z",
                "graph_snapshot_id": f"G{index % 3}",
                "split": split,
                "target": target,
                "debt_ratio": debt_ratio,
                "overdue_count": overdue_count,
                "company_age_years": years,
                "industry": f"I{index % 5}",
            }
        )
    samples_bytes = _csv_bytes(samples)
    target_name = "default_12m" if task_type == "loan_application" else "business_distress_12m"
    target_definition = (
        "申请后 12 个月内发生约定口径的逾期或违约"
        if task_type == "loan_application"
        else "观察时点后 12 个月内发生约定口径的经营异常"
    )
    payloads = {"samples.csv": samples_bytes}
    files: dict[str, object] = {
        "samples": {
            "path": "samples.csv",
            "format": "csv",
            "sizeBytes": len(samples_bytes),
            "sha256": hashlib.sha256(samples_bytes).hexdigest(),
        }
    }
    graph = None
    if include_graph:
        node_keys = sorted(
            {(str(row["graph_snapshot_id"]), str(row["entity_id"])) for row in samples}
        )
        nodes = [
            {"graph_snapshot_id": snapshot, "node_id": entity, "node_type": "company"}
            for snapshot, entity in node_keys
        ]
        relations = []
        hyperedges = []
        events = []
        by_snapshot: dict[str, list[str]] = {}
        for snapshot, entity in node_keys:
            by_snapshot.setdefault(snapshot, []).append(entity)
            hyperedges.append(
                {
                    "graph_snapshot_id": snapshot,
                    "hyperedge_id": f"industry-{int(entity[1:]) % 5}",
                    "hyperedge_type": "industry",
                    "node_id": entity,
                }
            )
            events.append(
                {
                    "graph_snapshot_id": snapshot,
                    "node_id": entity,
                    "event_type": "litigation" if int(entity[1:]) % 7 == 0 else "registry",
                    "event_time": "2024-01-01T00:00:00Z",
                    "amount": (int(entity[1:]) % 9) * 1000,
                }
            )
        for snapshot, entities in by_snapshot.items():
            for index, source in enumerate(entities):
                relations.append(
                    {
                        "graph_snapshot_id": snapshot,
                        "source_id": source,
                        "target_id": entities[(index + 1) % len(entities)],
                        "relation_type": "shared_address" if index % 2 else "ownership",
                        "weight": 1 + index % 3,
                    }
                )
        tables = {
            "nodes": _csv_bytes(nodes),
            "relations": _csv_bytes(relations),
            "events": _csv_bytes(events),
            "hyperedges": _csv_bytes(hyperedges),
        }
        for name, payload in tables.items():
            path = f"{name}.csv"
            payloads[path] = payload
            files[name] = {
                "path": path,
                "format": "csv",
                "sizeBytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        graph = {
            "snapshotMode": "external",
            "snapshotDefinition": "synthetic observation-time graph snapshots",
            "staticExperimentOnly": False,
        }
    metadata = {
        "schemaVersion": 1,
        "datasetName": f"synthetic-{task_type}",
        "taskType": task_type,
        "sampleUnit": task_type,
        "columns": {
            "sampleId": "sample_id",
            "entityId": "entity_id",
            "observationTime": "observation_time",
            "graphSnapshotId": "graph_snapshot_id",
            "split": "split",
            "target": "target",
        },
        "target": {
            "name": target_name,
            "positiveValue": 1,
            "predictionWindowDays": 365,
            "businessDefinition": target_definition,
        },
        "features": [
            {"name": "debt_ratio", "kind": "numeric", "group": "financial"},
            {"name": "overdue_count", "kind": "numeric", "group": "bureau"},
            {"name": "company_age_years", "kind": "numeric", "group": "registry"},
            {"name": "industry", "kind": "categorical", "group": "registry"},
        ],
        "files": files,
    }
    if graph is not None:
        metadata["graph"] = graph
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        for path, payload in payloads.items():
            archive.writestr(path, payload)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a deterministic Bundle v1 example")
    parser.add_argument("--output", required=True, help="destination .zip path")
    parser.add_argument(
        "--task",
        choices=("loan_application", "entity_snapshot"),
        default="loan_application",
    )
    parser.add_argument("--rows", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--with-graph", action="store_true")
    arguments = parser.parse_args()
    task_type = cast(Literal["loan_application", "entity_snapshot"], arguments.task)
    output = build_demo_bundle(
        arguments.output,
        task_type,
        rows=arguments.rows,
        seed=arguments.seed,
        include_graph=arguments.with_graph,
    )
    print(output)


if __name__ == "__main__":
    main()
