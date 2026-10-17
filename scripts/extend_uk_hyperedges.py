"""Version an independent graph with source-backed industry, postal and other hyperedges."""

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from finalize_uk_graph import group_view
from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from prepare_uk_graph import ROOT, graphml
from uk_graph.hyperedges import KINDS, SOURCE_DATE, common_parent_facts, group_id, snapshot_facts

BASE = ROOT / "outputs/uk-research-graph-20261017-v1"
OUTPUT = ROOT / "outputs/uk-research-graph-20261017-v2"
CLASSIFICATION = ROOT / "datasets/sources/uk-hyperedges-20261017/sic-codes.csv"
EVIDENCE_FIELDS = [
    "group_id",
    "node_id",
    "source_file",
    "source_record_number",
    "source_record_id",
    "source_fields",
    "source_values",
    "source_row_sha256",
]
GROUP_FIELDS = [
    "id",
    "kind",
    "member_count",
    "source_system",
    "source_date",
    "source_sha256",
    "historical_prediction_eligible",
    "value",
    "label",
    "semantic_kind",
    "family",
    "level",
    "parent_group_id",
    "membership_relation",
    "classification_sha256",
    "derivation",
]
ADDRESS_FIELDS = [
    "RegAddress." + field
    for field in (
        "AddressLine1",
        "AddressLine2",
        "PostTown",
        "County",
        "Country",
        "PostCode",
        "POBox",
    )
]


def raw_records(path):
    with gzip.open(path, "rt") as stream:
        for number, line in enumerate(stream, 1):
            record = json.loads(line)
            digest = hashlib.sha256(
                json.dumps(
                    record["row"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            if digest != record["row_sha256"]:
                raise ValueError("Original snapshot row checksum mismatch")
            yield number, record


def key_for(fact):
    return fact["kind"], fact["value"], fact.get("source_date", SOURCE_DATE)


def group_metadata(fact, members, snapshot_sha, classification_sha, node_names):
    kind, value, date = key_for(fact)
    semantic, family, level, relation = KINDS[kind]
    label = fact["label"]
    if semantic == "relational":
        label = label.replace(value, node_names[value])
    return {
        "id": group_id(kind, value, date),
        "kind": kind,
        "member_count": len(members),
        "source_system": "GLEIF" if semantic == "relational" else "Companies House",
        "source_date": date,
        "source_sha256": fact.get("source_sha256", snapshot_sha),
        "historical_prediction_eligible": False,
        "value": value,
        "label": label,
        "semantic_kind": semantic,
        "family": family,
        "level": level,
        "parent_group_id": fact.get("parent_group_id", ""),
        "membership_relation": relation,
        "classification_sha256": classification_sha if family == "industry" else "",
        "derivation": "group_children_of_same_reported_parent"
        if semantic == "relational"
        else "group_equal_source_attribute",
    }


def extend(base, output, classification):
    if output.exists() or output.resolve().is_relative_to(base.resolve()):
        raise ValueError("Choose a new output version outside the original graph")
    if not json.loads((base / "validation.json").read_text())["passed"]:
        raise ValueError("Base graph must have passed full validation")
    sic_codes = {
        row["SIC Code"].strip(): row["Description"].strip() for row in read_csv(classification)
    }
    classification_sha = sha(classification)
    nodes = list(read_csv(base / "nodes.csv"))
    node_names = {row["id"]: row["name"] for row in nodes}
    research = {row["id"] for row in nodes if row["is_research_company"] == "True"}
    edges = list(read_csv(base / "edges.csv"))
    snapshot_sha = json.loads((base / "source-manifest.json").read_text())["snapshotSha256"]
    buckets, facts_by_key = defaultdict(set), {}
    stats = Counter()
    for _, record in raw_records(base / "snapshot-raw-records.jsonl.gz"):
        if record["company_id"] not in research:
            raise ValueError("Snapshot record outside research scope")
        stats["snapshotCompanies"] += 1
        for fact in snapshot_facts(record["row"], sic_codes):
            key = key_for(fact)
            buckets[key].add(record["company_id"])
            facts_by_key[key] = fact
    parent_facts = list(common_parent_facts(edges))
    for fact in parent_facts:
        key = key_for(fact)
        buckets[key].add(fact["node_id"])
        facts_by_key[key] = fact
    admitted = {key: members for key, members in buckets.items() if len(members) >= 2}
    stats["singletonGroupsNotEmitted"] = sum(len(members) == 1 for members in buckets.values())
    skip = {
        "README.md",
        "delivery-manifest.json",
        "validation.json",
        "full-graph-export.json",
        "enterprise-and-address-groups.graphml",
        "graph-summary.json",
        "build-state.json",
        "uk-research-graph.md",
    }
    shutil.copytree(
        base, output, ignore=lambda directory, names: [name for name in names if name in skip]
    )
    shutil.copyfile(base / "graph-manifest.json", output / "base-graph-manifest.json")
    shutil.copyfile(base / "validation.json", output / "base-validation.json")
    classification_dir = output / "sources/classifications"
    classification_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(classification, classification_dir / "sic-codes.csv")
    shutil.copyfile(classification.with_name("source.json"), classification_dir / "sic-source.json")
    groups = []
    for row in read_csv(base / "groups.csv"):
        row.update(
            value="",
            label="",
            semantic_kind="attribute",
            family="postal_geography",
            level="address",
            parent_group_id="",
            membership_relation=KINDS[row["kind"]][3],
            classification_sha256="",
            derivation="group_equal_full_registered_address",
        )
        groups.append(row)
    new_groups = {
        key: group_metadata(
            facts_by_key[key], members, snapshot_sha, classification_sha, node_names
        )
        for key, members in sorted(admitted.items())
    }
    groups.extend(new_groups.values())
    group_ids = {row["id"] for row in groups}
    if len(group_ids) != len(groups):
        raise ValueError("Duplicate hyperedge identity")
    if any(row["parent_group_id"] and row["parent_group_id"] not in group_ids for row in groups):
        raise ValueError("Dangling classification hierarchy")
    memberships = list(read_csv(base / "group-memberships.csv"))
    address_members = {row["node_id"]: row["group_id"] for row in memberships}
    for key, members in sorted(admitted.items()):
        memberships.extend(
            {"group_id": new_groups[key]["id"], "node_id": member} for member in sorted(members)
        )
    write_csv(output / "groups.csv", groups, GROUP_FIELDS)
    write_csv(output / "group-memberships.csv", memberships, ["group_id", "node_id"])
    with (output / "membership-evidence.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVIDENCE_FIELDS)
        writer.writeheader()

        def emit(group, company, number, record_id, fields, values, digest, filename):
            writer.writerow(
                {
                    "group_id": group,
                    "node_id": company,
                    "source_file": filename,
                    "source_record_number": number,
                    "source_record_id": record_id,
                    "source_fields": json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
                    "source_values": json.dumps(values, ensure_ascii=False, separators=(",", ":")),
                    "source_row_sha256": digest,
                }
            )

        for number, record in raw_records(base / "snapshot-raw-records.jsonl.gz"):
            company, row = record["company_id"], record["row"]
            if company in address_members:
                emit(
                    address_members[company],
                    company,
                    number,
                    company,
                    ADDRESS_FIELDS,
                    [row.get(field, "") for field in ADDRESS_FIELDS],
                    record["row_sha256"],
                    "snapshot-raw-records.jsonl.gz",
                )
            for fact in snapshot_facts(row, sic_codes):
                key = key_for(fact)
                if key in new_groups:
                    emit(
                        new_groups[key]["id"],
                        company,
                        number,
                        company,
                        fact["source_fields"],
                        fact["source_values"],
                        record["row_sha256"],
                        "snapshot-raw-records.jsonl.gz",
                    )
        for fact in parent_facts:
            key = key_for(fact)
            if key in new_groups:
                emit(
                    new_groups[key]["id"],
                    fact["node_id"],
                    fact["source_record_number"],
                    fact["source_record_id"],
                    fact["source_fields"],
                    fact["source_values"],
                    fact["source_row_sha256"],
                    "edges.csv",
                )
    by_kind, members_by_kind, covered = Counter(), Counter(), defaultdict(set)
    kind_for = {row["id"]: row["kind"] for row in groups}
    for group in groups:
        by_kind[group["kind"]] += 1
    for row in memberships:
        kind = kind_for[row["group_id"]]
        members_by_kind[kind] += 1
        covered[kind].add(row["node_id"])
    write_csv(
        output / "hyperedge-type-summary.csv",
        (
            {
                "kind": kind,
                "hyperedges": by_kind[kind],
                "memberships": members_by_kind[kind],
                "unique_companies": len(covered[kind]),
                "research_companies": len(covered[kind] & research),
                "largest_hyperedge": max(
                    int(row["member_count"]) for row in groups if row["kind"] == kind
                ),
            }
            for kind in sorted(by_kind)
        ),
        [
            "kind",
            "hyperedges",
            "memberships",
            "unique_companies",
            "research_companies",
            "largest_hyperedge",
        ],
    )
    group_nodes, member_edges = group_view(nodes, groups, memberships)
    temporary = output / ".hyperedge-graphml"
    temporary.mkdir()
    try:
        graphml(temporary, nodes + group_nodes, edges + member_edges)
        (temporary / "enterprise-graph.graphml").replace(
            output / "enterprise-and-hyperedges.graphml"
        )
    finally:
        shutil.rmtree(temporary)
    connected = {row["node_id"] for row in memberships} | {
        row[field] for row in edges for field in ("source", "target")
    }
    summary = json.loads((base / "graph-summary.json").read_text())
    summary.update(
        hyperedges=len(groups),
        hyperedgeMemberships=len(memberships),
        hyperedgesByType=by_kind,
        membershipsByType=members_by_kind,
        isolatedResearchCompanies=len(research - connected),
        addressGroups=by_kind["shared_registered_address"],
        addressMemberships=members_by_kind["shared_registered_address"],
    )
    write_json(output / "graph-summary.json", summary)
    write_json(
        output / "full-graph-export.json",
        {
            "file": "enterprise-and-hyperedges.graphml",
            "companyNodes": len(nodes),
            "hyperedgeNodes": len(groups),
            "membershipEdges": len(memberships),
            "parentRelationships": len(edges),
            "sha256": sha(output / "enterprise-and-hyperedges.graphml"),
            "membershipDirectionIsSerializationOnlyNotOwnership": True,
        },
    )
    original = json.loads((base / "graph-manifest.json").read_text())
    original.update(
        format="uk-research-graph-hyperedges-v2",
        parentVersion=str(base),
        fullGraphml="enterprise-and-hyperedges.graphml",
        hyperedgeKinds=sorted(by_kind),
        hierarchyIsTaxonomyNotOwnership=True,
        postcodeDirectoryGeocodingVerified=False,
        allHyperedgesHistoricalPredictionEligible=False,
    )
    write_json(output / "graph-manifest.json", original)
    write_json(
        output / "hyperedge-manifest.json",
        {
            "baseDirectory": str(base),
            "baseValidationSha256": sha(base / "validation.json"),
            "preservedFiles": {
                str(path.relative_to(base)): sha(path)
                for path in sorted(base.rglob("*"))
                if path.is_file()
                and "code" not in path.relative_to(base).parts
                and path.name not in skip
                and path.name not in {"groups.csv", "group-memberships.csv", "graph-manifest.json"}
            },
            "classificationSha256": classification_sha,
            "snapshotDate": SOURCE_DATE,
            "audit": stats,
            "policy": {
                "minimumMembers": 2,
                "missingValueGroupCreated": False,
                "excludedSicCodes": ["74990", "99999"],
                "eventIndustryUsed": False,
                "parentGroupsContainChildrenOnly": True,
                "financialSimilarityOrOutcomeStatusGroupsCreated": False,
            },
            "codeFiles": {
                str(path.relative_to(ROOT)): sha(path)
                for path in [
                    Path(__file__),
                    ROOT / "scripts/uk_graph/hyperedges.py",
                    ROOT / "scripts/finalize_uk_graph.py",
                ]
            },
        },
    )
    print(
        json.dumps(
            {
                "hyperedgesByType": by_kind,
                "membershipsByType": members_by_kind,
                "isolatedResearchCompanies": summary["isolatedResearchCompanies"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--sic-codes", type=Path, default=CLASSIFICATION)
    args = parser.parse_args()
    extend(args.base, args.output, args.sic_codes)
