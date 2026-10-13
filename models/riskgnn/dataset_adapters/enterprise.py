"""Readable, pre-transform data shared by model preparation and enterprise browsing."""

import json
import math
from collections.abc import Iterable
from pathlib import Path

FORMAT = "risk-enterprise-data-v1"


def attributes(names: list[str], values: Iterable) -> dict:
    return {
        name: None if value is None or not math.isfinite(float(value)) else float(value)
        for name, value in zip(names, values, strict=True)
    }


def feature_vector(values: dict, names: list[str]) -> list:
    return [values[name] for name in names]


def snapshot_records(snapshots: dict) -> Iterable[dict]:
    for split, snapshot in snapshots.items():
        for node in snapshot.nodes:
            yield {
                "kind": node.kind,
                "snapshot": split,
                "nodeId": node.id,
                "data": {
                    "name": None,
                    "attributes": attributes(snapshot.feature_names, node.features),
                    "community": node.community,
                    "label": node.label,
                    "split": node.split,
                },
            }
        for edge in snapshot.edges:
            yield {
                "kind": "edge",
                "snapshot": split,
                "source": edge.source,
                "target": edge.target,
                "data": edge.model_dump(exclude_none=True),
            }
        for group in snapshot.hyperedges:
            yield {
                "kind": "hyperedge",
                "snapshot": split,
                "members": group.members,
                "data": group.model_dump(exclude_none=True),
            }
        for event in snapshot.events:
            yield {
                "kind": "event",
                "snapshot": split,
                "source": event.company,
                "data": event.model_dump(exclude_none=True),
            }


def export(adapter, validated: Path, output: Path, inspection: dict) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    header = {
        "format": FORMAT,
        "datasetContract": inspection["datasetContract"],
        "sourceSha256": inspection["sha256"],
        "featureNames": inspection["features"],
        "target": inspection["datasetProfile"]["target"],
    }
    with output.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(header, ensure_ascii=False, allow_nan=False) + "\n")
        for record in adapter.enterprise_records(validated):
            counts[record["kind"]] = counts.get(record["kind"], 0) + 1
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    return {"format": FORMAT, "counts": counts}
