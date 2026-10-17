"""Graph semantics are independent of any application import or model adapter."""

import re
import unicodedata
from collections import defaultdict

from uk_graph.gleif import PARENT_TYPES, stable_id


def unique_matches(records):
    candidates = defaultdict(list)
    for item in records:
        status = item["record"]["attributes"]["registration"]["status"]
        if status not in {"DUPLICATE", "ANNULLED"}:
            candidates[item["company_id"]].append(item)
    matches, ambiguous = {}, {}
    for company, items in candidates.items():
        by_lei = {item["record"]["id"]: item for item in items}
        if len(by_lei) == 1:
            matches[company] = next(iter(by_lei.values()))
        else:
            ambiguous[company] = sorted(by_lei)
    return matches, ambiguous


def parent_relationship(row, reference_date):
    kind = row["Relationship.RelationshipType"]
    if kind not in PARENT_TYPES:
        return None, "other_relationship_type"
    child, parent = row["Relationship.StartNode.NodeID"], row["Relationship.EndNode.NodeID"]
    if (
        row["Relationship.StartNode.NodeIDType"] != "LEI"
        or row["Relationship.EndNode.NodeIDType"] != "LEI"
    ):
        return None, "non_lei_endpoint"
    if not all(re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", value) for value in (child, parent)):
        return None, "invalid_lei"
    if child == parent:
        return None, "self_parent"
    if row["Relationship.RelationshipStatus"] != "ACTIVE":
        return None, "not_reported_active"
    if row["Registration.RegistrationStatus"] not in {"PUBLISHED", "LAPSED"}:
        return None, "registration_not_usable"
    periods = [
        {
            "start": row.get(f"Relationship.Period.{i}.startDate", ""),
            "end": row.get(f"Relationship.Period.{i}.endDate", ""),
        }
        for i in range(1, 6)
        if row.get(f"Relationship.Period.{i}.periodType") == "RELATIONSHIP_PERIOD"
    ]
    variants = {(p["start"], p["end"]) for p in periods}
    if len(variants) > 1:
        return None, "conflicting_relationship_periods"
    start, end = next(iter(variants), ("", ""))
    if (start and start[:10] > reference_date) or (end and end[:10] < reference_date):
        return None, "outside_reported_relationship_period"
    return {
        "source_lei": child,
        "target_lei": parent,
        "relation": kind,
        "reported_status": row["Relationship.RelationshipStatus"],
        "registration_status": row["Registration.RegistrationStatus"],
        "valid_from": start,
        "valid_to": end,
        "registration_initial_date": row["Registration.InitialRegistrationDate"],
        "registration_last_update": row["Registration.LastUpdateDate"],
        "validation_sources": row["Registration.ValidationSources"],
        "validation_documents": row["Registration.ValidationDocuments"],
        "validation_reference": row["Registration.ValidationReference"],
    }, ""


def ancestors(roots, by_child):
    visited, frontier, selected = set(), set(roots), []
    while frontier:
        current = frontier - visited
        if not current:
            break
        visited.update(current)
        frontier = set()
        for child in sorted(current):
            for edge in by_child.get(child, []):
                selected.append(edge)
                frontier.add(edge["target_lei"])
    return visited, selected


def address_key(row):
    if row["snapshot_missing"] != "False":
        return ""
    fields = ("AddressLine1", "AddressLine2", "PostTown", "County", "Country", "PostCode")
    parts = [
        " ".join(
            unicodedata.normalize("NFKC", row.get("snapshot_RegAddress." + field, ""))
            .upper()
            .split()
        )
        for field in fields
    ]
    if not parts[0] or not parts[-1]:
        return ""
    return stable_id(parts)


def research_node(row, match, observation_ids, fallback_name=""):
    attributes = match["record"]["attributes"] if match else {}
    entity = attributes.get("entity", {})
    if row["snapshot_CompanyName"]:
        name, source, date = row["snapshot_CompanyName"], "companies_house_snapshot", "2026-09-30"
    elif entity.get("legalName", {}).get("name"):
        name, source, date = (
            entity["legalName"]["name"],
            "gleif_reference",
            match["evidence"]["publish_date"],
        )
    elif row["event_reference_company_name"]:
        name, source, date = (
            row["event_reference_company_name"],
            "event_record_reference",
            row["event_reference_reference_month"],
        )
    elif fallback_name:
        name, source, date = fallback_name, "selected_historical_report", ""
    else:
        name, source, date = row["company_id"], "company_id_fallback", ""
    return {
        "id": row["company_id"],
        "kind": "company",
        "name": name,
        "name_source": source,
        "name_source_date": date,
        "name_missing": source == "company_id_fallback",
        "company_number": row["company_id"],
        "lei": match["record"]["id"] if match else "",
        "is_research_company": True,
        "observation_count": len(observation_ids),
        "snapshot_missing": row["snapshot_missing"] == "True",
        "snapshot_legal_form": row["snapshot_CompanyCategory"],
        "snapshot_company_status": row["snapshot_CompanyStatus"],
        "snapshot_incorporation_date": row["snapshot_IncorporationDate"],
        "snapshot_sic2007": "|".join(
            row[f"snapshot_sic2007_{i}"] for i in range(1, 5) if row[f"snapshot_sic2007_{i}"]
        ),
        "snapshot_registered_address": ", ".join(
            row["snapshot_RegAddress." + field]
            for field in (
                "AddressLine1",
                "AddressLine2",
                "PostTown",
                "County",
                "Country",
                "PostCode",
            )
            if row["snapshot_RegAddress." + field]
        ),
        "snapshot_postcode": row["snapshot_RegAddress.PostCode"],
        "event_reference_sic2007": row["event_reference_sic07_5_digit"],
        "gleif_legal_name": entity.get("legalName", {}).get("name", ""),
        "gleif_entity_creation_date": entity.get("creationDate") or "",
        "gleif_entity_status": entity.get("status") or "",
        "gleif_jurisdiction": entity.get("jurisdiction") or "",
        "gleif_legal_form_code": (entity.get("legalForm") or {}).get("id") or "",
        "gleif_registered_address": ", ".join(
            (entity.get("legalAddress") or {}).get("addressLines", [])
        ),
        "gleif_source_response_sha256": match["evidence"]["response_sha256"] if match else "",
    }
