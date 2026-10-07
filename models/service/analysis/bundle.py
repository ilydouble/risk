from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import roc_auc_score

from service.datasets.bundle.data import CORE_COLUMNS, BundleData


def _safe_number(value: Any) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _iv(series: pd.Series, target: np.ndarray) -> float:
    values = series.copy()
    if pd.api.types.is_numeric_dtype(values):
        try:
            values = pd.qcut(values, q=min(10, values.nunique()), duplicates="drop")
        except ValueError:
            values = values.astype(str)
    values = values.astype("string").fillna("__MISSING__")
    table = pd.DataFrame({"value": values, "target": target}).groupby("value")["target"]
    good = table.apply(lambda item: int((item == 0).sum()))
    bad = table.apply(lambda item: int((item == 1).sum()))
    good_dist = (good + 0.5) / (good.sum() + 0.5 * len(good))
    bad_dist = (bad + 0.5) / (bad.sum() + 0.5 * len(bad))
    return float(((bad_dist - good_dist) * np.log(bad_dist / good_dist)).sum())


def _psi(train: pd.Series, other: pd.Series) -> float:
    if pd.api.types.is_numeric_dtype(train):
        clean = pd.to_numeric(train, errors="coerce").dropna()
        if clean.nunique() > 1:
            edges = np.unique(np.quantile(clean, np.linspace(0, 1, 11)))
            if len(edges) > 2:
                train_bins = pd.cut(
                    pd.to_numeric(train, errors="coerce"), edges, include_lowest=True
                )
                other_bins = pd.cut(
                    pd.to_numeric(other, errors="coerce"), edges, include_lowest=True
                )
            else:
                train_bins, other_bins = train.astype(str), other.astype(str)
        else:
            train_bins, other_bins = train.astype(str), other.astype(str)
    else:
        train_bins, other_bins = train.astype(str), other.astype(str)
    left = pd.Series(train_bins).astype("string").fillna("__MISSING__").value_counts(normalize=True)
    right = (
        pd.Series(other_bins).astype("string").fillna("__MISSING__").value_counts(normalize=True)
    )
    categories = left.index.union(right.index)
    expected = left.reindex(categories, fill_value=0).clip(lower=1e-6)
    actual = right.reindex(categories, fill_value=0).clip(lower=1e-6)
    return float(((actual - expected) * np.log(actual / expected)).sum())


def _feature_signal(data: BundleData) -> list[dict[str, Any]]:
    train = data.samples[data.samples["split"] == "train"]
    positive = str(data.metadata.target.positive_value)
    target = (train["target"].astype(str) == positive).astype(int).to_numpy()
    result: list[dict[str, Any]] = []
    for feature in data.metadata.features:
        series = train[feature.name]
        encoded: pd.Series
        auc: float | None = None
        if feature.kind == "numeric":
            encoded = pd.to_numeric(series, errors="coerce")
            filled = encoded.fillna(encoded.median() if encoded.notna().any() else 0)
            if filled.nunique() > 1:
                raw_auc = roc_auc_score(target, filled)
                auc = float(max(raw_auc, 1 - raw_auc))
            matrix = filled.to_numpy().reshape(-1, 1)
            discrete = False
        else:
            encoded = series.astype("string").fillna("__MISSING__")
            codes, _ = pd.factorize(encoded)
            matrix = codes.reshape(-1, 1)
            discrete = True
        mi = mutual_info_classif(matrix, target, discrete_features=discrete, random_state=42)[0]
        risk_by_missing = None
        if series.isna().any() and (~series.isna()).any():
            risk_by_missing = {
                "missing": float(target[series.isna().to_numpy()].mean()),
                "present": float(target[(~series.isna()).to_numpy()].mean()),
            }
        result.append(
            {
                "name": feature.name,
                "kind": feature.kind,
                "group": feature.group,
                "univariateAuc": auc,
                "iv": _safe_number(_iv(series, target)),
                "mutualInformation": _safe_number(mi),
                "missingRisk": risk_by_missing,
            }
        )
    return sorted(result, key=lambda item: item["mutualInformation"] or 0, reverse=True)


def _quality(data: BundleData) -> dict[str, Any]:
    frame = data.samples
    columns = []
    for feature in data.metadata.features:
        values = frame[feature.name]
        item: dict[str, Any] = {
            "name": feature.name,
            "kind": feature.kind,
            "group": feature.group,
            "missingCount": int(values.isna().sum()),
            "missingRate": float(values.isna().mean()),
            "uniqueCount": int(values.nunique(dropna=True)),
            "constant": bool(values.nunique(dropna=True) <= 1),
            "highCardinality": bool(values.nunique(dropna=True) > max(100, len(values) * 0.5)),
        }
        if feature.kind == "numeric":
            numeric = pd.to_numeric(values, errors="coerce")
            item["numeric"] = {
                "min": _safe_number(numeric.min()) if numeric.notna().any() else None,
                "max": _safe_number(numeric.max()) if numeric.notna().any() else None,
                "mean": _safe_number(numeric.mean()) if numeric.notna().any() else None,
                "std": _safe_number(numeric.std(ddof=0)) if numeric.notna().any() else None,
                "outlierCount": int(
                    ((numeric < numeric.quantile(0.01)) | (numeric > numeric.quantile(0.99))).sum()
                ),
            }
        else:
            item["topValues"] = [
                {"value": str(value), "count": int(count)}
                for value, count in values.astype("string").value_counts().head(10).items()
            ]
        columns.append(item)
    return {
        "rowCount": len(frame),
        "columnCount": len(frame.columns),
        "duplicateRows": int(frame.astype(str).duplicated().sum()),
        "duplicateSampleIds": int(frame["sample_id"].astype(str).duplicated().sum()),
        "columns": columns,
    }


def _split_profile(data: BundleData) -> dict[str, Any]:
    positive = str(data.metadata.target.positive_value)
    profile = {}
    for split, rows in data.samples.groupby("split"):
        target = rows["target"].astype(str) == positive
        profile[str(split)] = {
            "rows": len(rows),
            "positives": int(target.sum()),
            "positiveRate": float(target.mean()),
            "entities": int(rows["entity_id"].nunique()),
            "startTime": rows["observation_time"].min().isoformat(),
            "endTime": rows["observation_time"].max().isoformat(),
        }
    return profile


def _drift(data: BundleData) -> dict[str, Any]:
    train = data.samples[data.samples["split"] == "train"]
    output: dict[str, Any] = {"validation": [], "test": []}
    for split in output:
        other = data.samples[data.samples["split"] == split]
        output[split] = sorted(
            [
                {
                    "name": feature.name,
                    "psi": _safe_number(_psi(train[feature.name], other[feature.name])),
                }
                for feature in data.metadata.features
            ],
            key=lambda item: item["psi"] or 0,
            reverse=True,
        )
    return output


def _correlations(data: BundleData) -> list[dict[str, Any]]:
    numeric_names = [
        feature.name for feature in data.metadata.features if feature.kind == "numeric"
    ]
    if len(numeric_names) < 2:
        return []
    train = data.samples[data.samples["split"] == "train"][numeric_names]
    correlation = train.apply(pd.to_numeric, errors="coerce").corr()
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(numeric_names):
        for right in numeric_names[left_index + 1 :]:
            value = correlation.loc[left, right]
            if pd.notna(value):
                pairs.append({"left": left, "right": right, "correlation": float(value)})
    return sorted(pairs, key=lambda item: abs(float(item["correlation"])), reverse=True)[:50]


def _leakage_warnings(data: BundleData, signals: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings = []
    suspicious = ("target", "label", "outcome", "after_", "post_", "writeoff", "recovery")
    for feature in data.metadata.features:
        lowered = feature.name.casefold()
        if lowered.endswith("_id") or any(token in lowered for token in suspicious):
            warnings.append(
                {"feature": feature.name, "reason": "name suggests ID or post-outcome data"}
            )
    for signal in signals:
        if signal["univariateAuc"] is not None and signal["univariateAuc"] >= 0.995:
            warnings.append({"feature": signal["name"], "reason": "near-perfect training AUC"})
    return warnings


def _graph_profile(data: BundleData) -> dict[str, Any]:
    if data.nodes is None:
        return {"available": False}
    nodes = data.nodes
    relations = data.relations
    profile: dict[str, Any] = {
        "available": True,
        "snapshotCount": int(nodes["graph_snapshot_id"].nunique()),
        "nodeCount": len(nodes),
        "nodeTypes": Counter(nodes["node_type"].astype(str)),
        "relationCount": 0 if relations is None else len(relations),
        "eventCount": 0 if data.events is None else len(data.events),
        "hyperedgeMembershipCount": 0 if data.hyperedges is None else len(data.hyperedges),
    }
    if relations is not None:
        profile["relationTypes"] = Counter(relations["relation_type"].astype(str))
        degree = pd.concat([relations["source_id"], relations["target_id"]]).value_counts()
        company_nodes = set(data.samples["entity_id"].astype(str))
        profile["isolatedSampleEntities"] = len(company_nodes.difference(degree.index.astype(str)))
        profile["degree"] = {
            "mean": float(degree.mean()) if len(degree) else 0,
            "p95": float(degree.quantile(0.95)) if len(degree) else 0,
            "max": int(degree.max()) if len(degree) else 0,
        }
        parents: dict[tuple[str, str], tuple[str, str]] = {}

        def find(node: tuple[str, str]) -> tuple[str, str]:
            parents.setdefault(node, node)
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        def union(left: tuple[str, str], right: tuple[str, str]) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for row in nodes[["graph_snapshot_id", "node_id"]].astype(str).itertuples(index=False):
            find((row.graph_snapshot_id, row.node_id))
        for row in (
            relations[["graph_snapshot_id", "source_id", "target_id"]]
            .astype(str)
            .itertuples(index=False)
        ):
            union(
                (row.graph_snapshot_id, row.source_id),
                (row.graph_snapshot_id, row.target_id),
            )
        profile["connectedComponents"] = len({find(node) for node in parents})
    if data.hyperedges is not None:
        sizes = data.hyperedges.groupby(["graph_snapshot_id", "hyperedge_id"]).size()
        profile["hyperedgeCount"] = len(sizes)
        profile["hyperedgeSize"] = {
            "mean": float(sizes.mean()) if len(sizes) else 0,
            "max": int(sizes.max()) if len(sizes) else 0,
        }
    return profile


def analyze_bundle(data: BundleData) -> dict[str, Any]:
    signals = _feature_signal(data)
    return {
        "quality": _quality(data),
        "splits": _split_profile(data),
        "signals": signals,
        "drift": _drift(data),
        "correlations": _correlations(data),
        "leakageWarnings": _leakage_warnings(data, signals),
        "graph": _graph_profile(data),
        "excludedRawPreview": True,
        "reservedColumns": sorted(CORE_COLUMNS),
    }
