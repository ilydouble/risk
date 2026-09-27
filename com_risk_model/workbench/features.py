from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

from workbench.data import BundleData


@dataclass(frozen=True)
class FeatureSelection:
    selected: list[str]
    excluded: list[dict[str, str]]
    ranking: list[dict[str, Any]]
    configuration: dict[str, Any]


def _training_score(series: pd.Series, target: np.ndarray, numeric: bool) -> float:
    if numeric:
        values = pd.to_numeric(series, errors="coerce")
        filled = values.fillna(values.median() if values.notna().any() else 0)
        matrix = filled.to_numpy().reshape(-1, 1)
    else:
        codes, _ = pd.factorize(series.astype("string").fillna("__MISSING__"))
        matrix = codes.reshape(-1, 1)
    return float(
        mutual_info_classif(matrix, target, discrete_features=not numeric, random_state=42)[0]
    )


def select_features(
    data: BundleData,
    *,
    mode: str,
    manual: list[str],
    max_features: int = 50,
    missing_threshold: float = 0.95,
    correlation_threshold: float = 0.95,
) -> FeatureSelection:
    declared = {feature.name: feature for feature in data.metadata.features}
    if mode == "manual":
        unknown = set(manual).difference(declared)
        if not manual or unknown:
            raise ValueError(f"manual feature list is invalid: {sorted(unknown)}")
        return FeatureSelection(
            list(dict.fromkeys(manual)),
            [],
            [],
            {"mode": "manual", "fitSplit": "train"},
        )
    if mode != "recommended":
        raise ValueError("feature mode must be recommended or manual")
    train = data.samples[data.samples["split"] == "train"]
    target = (
        train["target"].astype(str) == str(data.metadata.target.positive_value)
    ).astype(int).to_numpy()
    excluded: list[dict[str, str]] = []
    candidates: list[str] = []
    scores: dict[str, float] = {}
    suspicious = re.compile(
        r"(^id$|_id$|target|label|outcome|after_|post_|writeoff|recovery)", re.I
    )
    for name, feature in declared.items():
        series = train[name]
        reason = None
        if suspicious.search(name):
            reason = "identifier_or_leakage_name"
        elif series.isna().all():
            reason = "all_missing"
        elif series.isna().mean() > missing_threshold:
            reason = "missing_rate"
        elif series.nunique(dropna=True) <= 1:
            reason = "constant"
        if reason:
            excluded.append({"name": name, "reason": reason})
            continue
        candidates.append(name)
        scores[name] = _training_score(series, target, feature.kind == "numeric")
    numeric = [name for name in candidates if declared[name].kind == "numeric"]
    if len(numeric) > 1:
        correlation = train[numeric].apply(pd.to_numeric, errors="coerce").corr().abs()
        ordered = sorted(numeric, key=lambda name: scores[name], reverse=True)
        kept: list[str] = []
        for name in ordered:
            redundant = next(
                (
                    other
                    for other in kept
                    if pd.notna(correlation.loc[name, other])
                    and correlation.loc[name, other] >= correlation_threshold
                ),
                None,
            )
            if redundant:
                candidates.remove(name)
                excluded.append({"name": name, "reason": f"correlated_with:{redundant}"})
            else:
                kept.append(name)
    ranking: list[dict[str, Any]] = sorted(
        [{"name": name, "mutualInformation": scores[name]} for name in candidates],
        key=lambda item: float(item["mutualInformation"]),
        reverse=True,
    )
    selected = [str(item["name"]) for item in ranking[:max_features]]
    if not selected:
        raise ValueError("no eligible features remain after training-only selection")
    for item in ranking[max_features:]:
        excluded.append({"name": str(item["name"]), "reason": "ranking_limit"})
    return FeatureSelection(
        selected,
        excluded,
        ranking,
        {
            "mode": "recommended",
            "fitSplit": "train",
            "missingThreshold": missing_threshold,
            "correlationThreshold": correlation_threshold,
            "maxFeatures": max_features,
        },
    )


def graph_statistics(data: BundleData) -> pd.DataFrame:
    if data.nodes is None or data.relations is None:
        raise ValueError("relations are required for graph statistics")
    samples = data.samples[["sample_id", "entity_id", "graph_snapshot_id", "split", "target"]]
    relations = data.relations.copy()
    relations["graph_snapshot_id"] = relations["graph_snapshot_id"].astype(str)
    relations["source_id"] = relations["source_id"].astype(str)
    relations["target_id"] = relations["target_id"].astype(str)
    relations["relation_type"] = relations["relation_type"].astype(str)
    snapshots = samples["graph_snapshot_id"].astype(str)
    entities = samples["entity_id"].astype(str)
    outgoing = relations.groupby(["graph_snapshot_id", "source_id"]).agg(
        graph_out_degree=("target_id", "size"), graph_out_weight=("weight", "sum")
    )
    incoming = relations.groupby(["graph_snapshot_id", "target_id"]).agg(
        graph_in_degree=("source_id", "size"), graph_in_weight=("weight", "sum")
    )
    keys = pd.MultiIndex.from_arrays([snapshots, entities])
    features = pd.DataFrame(index=samples.index)
    for frame in (outgoing, incoming):
        aligned = frame.reindex(keys).reset_index(drop=True).fillna(0)
        for column in aligned:
            features[column] = aligned[column].to_numpy(dtype=float)
    endpoints = pd.concat(
        [
            relations[["graph_snapshot_id", "source_id", "relation_type"]].rename(
                columns={"source_id": "node_id"}
            ),
            relations[["graph_snapshot_id", "target_id", "relation_type"]].rename(
                columns={"target_id": "node_id"}
            ),
        ],
        ignore_index=True,
    )
    relation_counts = endpoints.groupby(
        ["graph_snapshot_id", "node_id", "relation_type"]
    ).size().unstack(fill_value=0)
    for index, relation_type in enumerate(sorted(relation_counts.columns.astype(str))):
        aligned = relation_counts[relation_type].reindex(keys, fill_value=0)
        safe_type = re.sub(r"[^a-zA-Z0-9]+", "_", relation_type).strip("_")[:32]
        features[f"graph_relation_{index}_{safe_type}_count"] = aligned.to_numpy(dtype=float)
    train = samples[samples["split"] == "train"].copy()
    train["graph_snapshot_id"] = train["graph_snapshot_id"].astype(str)
    train["entity_id"] = train["entity_id"].astype(str)
    train["risk"] = (
        train["target"].astype(str) == str(data.metadata.target.positive_value)
    ).astype(float)
    entity_risk = train.groupby(["graph_snapshot_id", "entity_id"])["risk"].mean().to_dict()
    global_risk = float(train["risk"].mean())
    adjacency: dict[tuple[str, str], list[str]] = {}
    for row in relations.itertuples(index=False):
        source_key = (str(row.graph_snapshot_id), str(row.source_id))
        target_key = (str(row.graph_snapshot_id), str(row.target_id))
        adjacency.setdefault(source_key, []).append(target_key[1])
        adjacency.setdefault(target_key, []).append(source_key[1])
    neighbor_risk = []
    neighbor_labeled = []
    for snapshot, entity in zip(snapshots, entities, strict=True):
        values = [
            entity_risk[(snapshot, neighbor)]
            for neighbor in adjacency.get((snapshot, entity), [])
            if (snapshot, neighbor) in entity_risk
        ]
        neighbor_labeled.append(len(values))
        neighbor_risk.append((sum(values) + 5 * global_risk) / (len(values) + 5))
    features["graph_labeled_neighbor_count"] = neighbor_labeled
    features["graph_neighbor_risk_prior"] = neighbor_risk
    if data.hyperedges is not None:
        memberships = data.hyperedges.copy()
        sizes = memberships.groupby(["graph_snapshot_id", "hyperedge_id"]).size()
        memberships["size"] = [
            sizes[(snapshot, edge)]
            for snapshot, edge in zip(
                memberships["graph_snapshot_id"], memberships["hyperedge_id"], strict=True
            )
        ]
        by_node = memberships.groupby(["graph_snapshot_id", "node_id"])["size"].agg(
            ["count", "max", "mean"]
        )
        aligned = by_node.reindex(keys).reset_index(drop=True).fillna(0)
        features["graph_hyperedge_count"] = aligned["count"].to_numpy(dtype=float)
        features["graph_hyperedge_max_size"] = aligned["max"].to_numpy(dtype=float)
        features["graph_hyperedge_mean_size"] = aligned["mean"].to_numpy(dtype=float)
    features.insert(0, "sample_id", samples["sample_id"].astype(str).to_numpy())
    return features
