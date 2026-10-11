from typing import Any

import pandas as pd


def _number(value: Any) -> int:
    return int(value) if pd.notna(value) else 0


def debug_samples(
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
