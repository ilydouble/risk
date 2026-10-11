from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

PREFIX = "comrisk_export/"
REQUIRED_FILES = {
    "company_attr.parquet",
    "edges.parquet",
    "export_meta.json",
    "hypergraph_area.parquet",
    "hypergraph_industry.parquet",
    "hypergraph_qualify.parquet",
    "label.parquet",
    "risk_data.parquet",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.filename in members:
            raise ValueError(f"duplicate ZIP member: {info.filename}")
        if info.flag_bits & 0x1:
            raise ValueError("encrypted ZIP members are not supported")
        members[info.filename] = info
    missing = [name for name in REQUIRED_FILES if f"{PREFIX}{name}" not in members]
    if missing:
        raise ValueError(f"missing ComRisk export files: {sorted(missing)}")
    return members


def _read_parquet(
    archive: zipfile.ZipFile, name: str, *, columns: list[str] | None = None
) -> pd.DataFrame:
    payload = io.BytesIO(archive.read(f"{PREFIX}{name}"))
    return pd.read_parquet(payload, columns=columns)


def _parquet_rows(archive: zipfile.ZipFile, name: str) -> int:
    payload = io.BytesIO(archive.read(f"{PREFIX}{name}"))
    return pq.ParquetFile(payload).metadata.num_rows


def _number(value: Any) -> int:
    return int(value) if pd.notna(value) else 0


def _debug_samples(
    attributes: pd.DataFrame,
    labels: pd.DataFrame,
    edges: pd.DataFrame,
    hypergraphs: dict[str, pd.DataFrame],
    *,
    per_class: int,
) -> list[dict[str, Any]]:
    fact_columns = [
        "company_id",
        "name",
        "country",
        "setup_time_months",
        "age_years",
        "ssic_code",
        "ssic2",
        "officers",
        "name_change_count",
        "has_unit",
        "register_capital",
        "paid_capital",
    ]
    records = attributes[fact_columns].merge(
        labels[["company_id", "label", "status_detail"]],
        on="company_id",
        validate="one_to_one",
    )
    records["label_category"] = "unlabeled"
    records.loc[records["label"] == 0, "label_category"] = "healthy"
    records.loc[records["label"] == 1, "label_category"] = "distress"
    records["sample_rank"] = pd.util.hash_pandas_object(
        records["company_id"].astype(str), index=False
    )
    selected = pd.concat(
        [
            records[records["label_category"] == category].nsmallest(per_class, "sample_rank")
            for category in ("distress", "healthy", "unlabeled")
        ],
        ignore_index=True,
    ).sort_values("sample_rank")
    sample_ids = set(selected["company_id"].astype(str))
    edge_mask = edges["src_id"].astype(str).isin(sample_ids) | edges["dst_id"].astype(str).isin(
        sample_ids
    )
    sample_edges = edges.loc[edge_mask].copy()
    neighbor_ids = set(sample_edges["src_id"].astype(str)) | set(sample_edges["dst_id"].astype(str))
    neighbor_attributes = attributes.loc[
        attributes["company_id"].astype(str).isin(neighbor_ids), ["company_id", "name"]
    ]
    neighbor_labels = labels.loc[
        labels["company_id"].astype(str).isin(neighbor_ids),
        ["company_id", "label", "status_detail"],
    ]
    neighbor_meta = neighbor_attributes.merge(
        neighbor_labels, on="company_id", how="left", validate="one_to_one"
    ).set_index("company_id")

    relations_by_company: dict[str, list[dict[str, Any]]] = {
        company_id: [] for company_id in sample_ids
    }
    for edge in sample_edges.itertuples(index=False):
        source_id = str(edge.src_id)
        target_id = str(edge.dst_id)
        for company_id, neighbor_id in ((source_id, target_id), (target_id, source_id)):
            if company_id not in sample_ids:
                continue
            meta = neighbor_meta.loc[neighbor_id]
            label = meta["label"]
            category = "unlabeled"
            if label == 0:
                category = "healthy"
            elif label == 1:
                category = "distress"
            relations_by_company[company_id].append(
                {
                    "companyId": neighbor_id,
                    "name": str(meta["name"]),
                    "status": (
                        str(meta["status_detail"])
                        if pd.notna(meta["status_detail"])
                        else "(missing)"
                    ),
                    "labelCategory": category,
                    "relationType": str(edge.rel_type),
                    "weight": float(edge.weight),
                }
            )

    memberships: dict[str, list[dict[str, Any]]] = {company_id: [] for company_id in sample_ids}
    for group_type in ("industry", "area", "qualify"):
        frame = hypergraphs[group_type]
        sizes = frame["group_value"].value_counts(dropna=True)
        sample_memberships = frame.loc[frame["company_id"].astype(str).isin(sample_ids)]
        for membership in sample_memberships.itertuples(index=False):
            if pd.isna(membership.group_value):
                continue
            value = str(membership.group_value)
            memberships[str(membership.company_id)].append(
                {
                    "type": group_type,
                    "value": value,
                    "memberCount": int(sizes.get(membership.group_value, 0)),
                }
            )

    samples: list[dict[str, Any]] = []
    for row in selected.itertuples(index=False):
        company_id = str(row.company_id)
        relations = sorted(
            relations_by_company[company_id],
            key=lambda item: (-item["weight"], item["relationType"], item["companyId"]),
        )
        relation_counts = pd.Series(
            [item["relationType"] for item in relations], dtype="string"
        ).value_counts()
        samples.append(
            {
                "companyId": company_id,
                "name": str(row.name),
                "labelCategory": str(row.label_category),
                "status": (str(row.status_detail) if pd.notna(row.status_detail) else "(missing)"),
                "ageYears": float(row.age_years) if pd.notna(row.age_years) else None,
                "industryCode": str(row.ssic_code) if pd.notna(row.ssic_code) else None,
                "relationCount": len(relations),
                "facts": {
                    "country": str(row.country) if pd.notna(row.country) else None,
                    "setupTimeMonths": (
                        float(row.setup_time_months) if pd.notna(row.setup_time_months) else None
                    ),
                    "industryDivisionCode": (str(row.ssic2) if pd.notna(row.ssic2) else None),
                    "officerCount": int(row.officers) if pd.notna(row.officers) else None,
                    "nameChangeCount": (
                        int(row.name_change_count) if pd.notna(row.name_change_count) else None
                    ),
                    "hasUnit": bool(row.has_unit) if pd.notna(row.has_unit) else None,
                    "registeredCapital": (
                        float(row.register_capital) if pd.notna(row.register_capital) else None
                    ),
                    "paidCapital": (
                        float(row.paid_capital) if pd.notna(row.paid_capital) else None
                    ),
                },
                "relationProfile": {
                    "totalCount": len(relations),
                    "byType": [
                        {"type": str(relation_type), "count": int(count)}
                        for relation_type, count in relation_counts.items()
                    ],
                    "neighbors": relations[:12],
                    "displayedCount": min(len(relations), 12),
                    "truncated": len(relations) > 12,
                },
                "groups": memberships[company_id],
                "dataAvailability": {
                    "registry": "available",
                    "relations": "available" if relations else "no_records",
                    "capital": "source_unavailable",
                    "litigation": "source_unavailable",
                    "bankCredit": "not_in_dataset",
                    "modelRisk": "not_run",
                },
            }
        )
    return samples


def build_singapore_overview(source: str | Path, *, sample_per_class: int = 100) -> dict[str, Any]:
    if sample_per_class < 1 or sample_per_class > 1000:
        raise ValueError("sample_per_class must be between 1 and 1000")
    path = Path(source)
    archive_sha256 = _sha256(path)
    with zipfile.ZipFile(path) as archive:
        _members(archive)
        export_meta = json.loads(archive.read(f"{PREFIX}export_meta.json"))
        labels = _read_parquet(
            archive,
            "label.parquet",
            columns=["company_id", "label", "is_labeled", "status_detail"],
        )
        attributes = _read_parquet(
            archive,
            "company_attr.parquet",
            columns=[
                "company_id",
                "name",
                "country",
                "setup_time_months",
                "age_years",
                "ssic_code",
                "ssic2",
                "officers",
                "name_change_count",
                "has_unit",
                "register_capital",
                "paid_capital",
            ],
        )
        edges = _read_parquet(
            archive,
            "edges.parquet",
            columns=["src_id", "dst_id", "rel_type", "weight"],
        )
        hypergraphs = {
            name: _read_parquet(
                archive,
                f"hypergraph_{name}.parquet",
                columns=["company_id", "group_value"],
            )
            for name in ("industry", "area", "qualify")
        }
        litigation_rows = _parquet_rows(archive, "risk_data.parquet")

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
            "total": _number(row.total),
            "labeled": _number(row.labeled),
            "distress": _number(row.distress),
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
    sample_companies = _debug_samples(
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
            "id": "sg-comrisk-v2-profile-v1-20260927",
            "name": "Singapore ACRA/GLEIF ComRisk Export v2.0",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a real Singapore overview snapshot")
    parser.add_argument("--source", type=Path, required=True, help="ComRisk v2 export ZIP")
    parser.add_argument("--output", type=Path, required=True, help="Output aggregate JSON")
    parser.add_argument(
        "--sample-per-class",
        type=int,
        default=100,
        help="Deterministic debug samples for each label category",
    )
    arguments = parser.parse_args()
    snapshot = build_singapore_overview(
        arguments.source, sample_per_class=arguments.sample_per_class
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(arguments.output)


if __name__ == "__main__":
    main()
