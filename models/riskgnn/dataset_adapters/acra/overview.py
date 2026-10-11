from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from riskgnn.dataset_adapters.acra.overview_samples import debug_samples
from riskgnn.dataset_adapters.acra.paths import data_root
from riskgnn.dataset_adapters.acra.validation import verify_validated


def build_singapore_overview(source: str | Path, *, sample_per_class: int = 100) -> dict[str, Any]:
    if sample_per_class < 1 or sample_per_class > 1000:
        raise ValueError("sample_per_class must be between 1 and 1000")
    path = Path(source)
    manifest = verify_validated(path)
    root = data_root(path)
    archive_sha256 = manifest["sha256"]
    export_meta = manifest["source"]
    labels = pd.read_parquet(root / "label.parquet")
    attributes = pd.read_parquet(root / "company_attr.parquet")
    edges = pd.read_parquet(
        root / "edges.parquet", columns=["src_id", "dst_id", "rel_type", "weight"]
    )
    hypergraphs = {
        name: pd.read_parquet(
            root / f"hypergraph_{name}.parquet", columns=["company_id", "group_value"]
        )
        for name in ("industry", "area", "qualify")
    }
    litigation_rows = pq.ParquetFile(root / "risk_data.parquet").metadata.num_rows

    if labels["company_id"].duplicated().any() or attributes["company_id"].duplicated().any():
        raise ValueError("company_id must be unique in label and company_attr")
    if len(labels) != len(attributes):
        raise ValueError("label and company_attr row counts must match")

    labeled_mask = labels["is_labeled"] == 1
    positive_mask = labels["label"] == 1
    negative_mask = labels["label"] == 0
    company_count = len(labels)
    labeled_count = int(labeled_mask.sum())
    distress_count = int(positive_mask.sum())
    healthy_count = int(negative_mask.sum())
    unlabeled_count = company_count - labeled_count

    joined = attributes[["company_id", "age_years"]].merge(
        labels[["company_id", "label", "is_labeled"]],
        on="company_id",
        validate="one_to_one",
    )
    joined["bucket"] = pd.cut(
        pd.to_numeric(joined["age_years"], errors="coerce"),
        bins=[-1, 3, 10, 20, 50, float("inf")],
        labels=["0_3", "4_10", "11_20", "21_50", "50_plus"],
    )
    age_rows = (
        joined.dropna(subset=["bucket"])
        .groupby("bucket", observed=True)
        .agg(
            total=("company_id", "size"),
            labeled=("is_labeled", "sum"),
            distress=("label", lambda values: int((values == 1).sum())),
        )
        .reset_index()
    )
    age_distribution = [
        {
            "bucket": str(row.bucket),
            "total": int(row.total),
            "labeled": int(row.labeled),
            "distress": int(row.distress),
        }
        for row in age_rows.itertuples(index=False)
    ]

    status_distribution = [
        {"status": str(status) if str(status) else "(blank)", "count": int(count)}
        for status, count in labels["status_detail"].fillna("(missing)").value_counts().items()
    ]
    edge_types = [
        {"type": str(relation_type), "count": int(count)}
        for relation_type, count in edges["rel_type"].value_counts().items()
    ]
    endpoints = set(edges["src_id"].astype(str)) | set(edges["dst_id"].astype(str))
    labeled_edge_count = int(
        labels.loc[labeled_mask, "company_id"].astype(str).isin(endpoints).sum()
    )
    graph_components = [
        {
            "key": "relations",
            "rowCount": len(edges),
            "groupCount": int(edges["rel_type"].nunique()),
        },
        *[
            {
                "key": name,
                "rowCount": len(frame),
                "groupCount": int(frame["group_value"].nunique(dropna=True)),
            }
            for name, frame in hypergraphs.items()
        ],
    ]
    sample_companies = debug_samples(
        attributes,
        labels,
        edges,
        hypergraphs,
        per_class=sample_per_class,
    )
    generated_at = str(export_meta.get("generated_at", ""))
    return {
        "snapshotVersion": 1,
        "dataset": {
            "id": "acra-" + archive_sha256[:16],
            "name": "Singapore ACRA/GLEIF " + manifest["datasetContract"]["dataset"]["version"],
            "country": "SG",
            "taskType": "entity_status_distress",
            "generatedAt": generated_at,
            "sourceScope": str(export_meta.get("scope", "Singapore only")),
            "sourceArchiveSha256": archive_sha256,
        },
        "stats": {
            "companyCount": company_count,
            "labeledCount": labeled_count,
            "distressCount": distress_count,
            "healthyCount": healthy_count,
            "unlabeledCount": unlabeled_count,
            "edgeCount": len(edges),
        },
        "labelDistribution": [
            {"key": "healthy", "value": healthy_count},
            {"key": "distress", "value": distress_count},
            {"key": "unlabeled", "value": unlabeled_count},
        ],
        "ageDistribution": age_distribution,
        "statusDistribution": status_distribution,
        "edgeTypes": edge_types,
        "graphComponents": graph_components,
        "sampling": {
            "strategy": "deterministic_stratified_hash",
            "requestedPerClass": sample_per_class,
            "sampleCount": len(sample_companies),
            "representative": False,
        },
        "sampleCompanies": sample_companies,
        "quality": {
            "labeledRate": labeled_count / company_count,
            "distressRateWithinLabeled": distress_count / labeled_count,
            "ordinaryEdgeCoverageWithinLabeled": labeled_edge_count / labeled_count,
            "capitalCoverage": float(
                (attributes["register_capital"].notna() | attributes["paid_capital"].notna()).mean()
            ),
            "litigationRows": litigation_rows,
        },
        "warnings": [
            "singapore_only_not_loan_default",
            "administrative_terminations_unlabeled",
            "age_time_confound",
            "weak_address_graph",
            "capital_litigation_unavailable",
        ],
    }
