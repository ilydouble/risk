"""Reconstruct the published UK and SMEsD snapshot representations."""

import json
from pathlib import Path

import pyarrow.parquet as pq

from riskgnn.workbench.artifacts import read_json

SMESD_EDGE_FIELDS = (
    "source",
    "target",
    "relation",
    "weight",
    "relation_id",
    "strength",
    "existence_confidence",
    "source_system",
    "evidence_count",
    "observed_at",
    "valid_from",
    "valid_to",
    "is_inferred",
    "relation_kind",
)
SMESD_GROUP_FIELDS = (
    "kind",
    "hyperedge_confidence",
    "source_system",
    "semantic_kind",
    "is_inferred",
    "recommended",
    "recommendation_note",
)
SMESD_EVENT_FIELDS = ("company", "cause", "court", "result", "age_months")


def restore_uk(package: Path, destination: Path, split: str) -> None:
    def rows(name):
        return pq.read_table(package / f"{split}_{name}.parquet").to_pylist()

    snapshot = read_json(package / f"{split}_snapshot.json")
    observations, labels = rows("observations"), rows("labels")
    nodes = []
    for observation, label in zip(observations, labels, strict=True):
        sample = observation["sample_id"]
        if label["sample_id"] != sample:
            raise ValueError("The label table does not align with observations")
        nodes.append(
            {
                "id": sample,
                "kind": "company",
                "name": observation["name"],
                "community": observation["community"],
                "features": observation["features"],
                "label": label["label"],
                "split": label["split"],
                "properties": {
                    "sample_id": sample,
                    "company_id": observation["company_id"],
                    "pair_id": observation["pair_id"],
                    "observation_month": observation["observation_month"],
                    "followup_end_month": observation["followup_end_month"],
                    "prediction_horizon_months": observation["prediction_horizon_months"],
                },
            }
        )
    groups = [
        {"kind": row["kind"], "members": [], "source_system": row["source_system"]}
        for row in rows("groups")
    ]
    for row in rows("memberships"):
        members = groups[row["group_id"]]["members"]
        if len(members) != row["position"]:
            raise ValueError("The group membership order changed")
        members.append(row["sample_id"])
    snapshot.update(nodes=nodes, hyperedges=groups)
    write_snapshot(destination, snapshot)


def restore_smesd(package: Path, destination: Path, split: str) -> None:
    def rows(name):
        return pq.read_table(package / f"{split}_{name}.parquet").to_pylist()

    entities = pq.read_table(
        package / "entities.parquet", filters=[("snapshot", "=", split)]
    ).to_pylist()
    observations = {row["company_id"]: row for row in rows("observations")}
    labels = {row["sample_id"]: row for row in rows("labels")}
    nodes = []
    for entity in sorted(entities, key=lambda row: row["position"]):
        company = observations.get(entity["node_id"])
        label = labels[company["sample_id"]] if company else {"label": None, "split": None}
        nodes.append(
            {
                "id": entity["node_id"],
                "kind": entity["kind"],
                "community": entity["community"],
                "features": company["features"] if company else entity["context_features"],
                "label": label["label"],
                "split": label["split"],
            }
        )

    groups = {row["group_id"]: row for row in rows("groups")}
    members = {group: [] for group in groups}
    for row in sorted(rows("memberships"), key=lambda row: (row["group_id"], row["position"])):
        members[row["group_id"]].append(row)
    hyperedges = [
        {
            "kind": groups[group]["kind"],
            "members": [row["sample_id"] for row in members[group]],
            "hyperedge_confidence": groups[group]["hyperedge_confidence"],
            "membership_confidence": [row["membership_confidence"] for row in members[group]],
            **{key: groups[group][key] for key in list(SMESD_GROUP_FIELDS)[2:]},
        }
        for group in sorted(groups)
    ]
    snapshot = read_json(package / f"{split}_snapshot.json")
    snapshot.update(
        nodes=nodes,
        edges=[
            {key: row[key] for key in SMESD_EDGE_FIELDS}
            for row in sorted(rows("edges"), key=lambda row: row["position"])
        ],
        hyperedges=hyperedges,
        events=[
            {key: row[key] for key in SMESD_EVENT_FIELDS}
            for row in sorted(rows("events"), key=lambda row: row["event_id"])
        ],
    )
    write_snapshot(destination, snapshot)


def write_snapshot(destination: Path, snapshot: dict) -> None:
    destination.write_text(
        json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
        encoding="utf-8",
    )
