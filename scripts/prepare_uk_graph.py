"""Build an independent graph for the rebuilt UK research cohort and its parents."""

import argparse
import csv
import gzip
import io
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from uk_graph.core import address_key, ancestors, parent_relationship, research_node, unique_matches
from uk_graph.gleif import (
    download_relationships,
    fetch_companies,
    fetch_leis,
    registered_company,
    stable_id,
)

ROOT = Path(__file__).resolve().parents[1]
BASIC = ROOT / "datasets/archive/uk-research-20261017/uk-basic-information-20261017-v1"
EVENTS = ROOT / "datasets/archive/uk-research-20261017/uk-adverse-events-2020-2025-v1/events.csv"
SOURCE = ROOT / "datasets/sources/gleif-20261017"
OUTPUT = ROOT / "datasets/archive/uk-research-20261017/uk-research-graph-20261017-v1"


def relationship_records(path):
    with ZipFile(path) as archive:
        members = [p for p in archive.namelist() if p.endswith(".csv")]
        if len(members) != 1 or archive.testzip() is not None:
            raise ValueError("Expected one intact GLEIF relationship CSV")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            for number, row in enumerate(reader, 2):
                if None in row or None in row.values():
                    raise ValueError("Malformed GLEIF relationship CSV")
                yield (
                    row,
                    {"member": members[0], "record_number": number, "row_sha256": stable_id(row)},
                )


def parent_node(lei, item, fields):
    result = dict.fromkeys(fields, "")
    result.update(
        id="LEI:" + lei,
        kind="company",
        lei=lei,
        is_research_company=False,
        observation_count=0,
        name=lei,
        name_missing=True,
        name_source="lei_fallback",
        snapshot_missing=True,
    )
    if item:
        attributes = item["record"]["attributes"]
        entity = attributes["entity"]
        result.update(
            name=entity["legalName"]["name"] or lei,
            name_missing=not bool(entity["legalName"]["name"]),
            company_number=registered_company(item["record"]),
            name_source="gleif_reference",
            name_source_date=item["evidence"]["publish_date"],
            gleif_legal_name=entity["legalName"]["name"],
            gleif_entity_creation_date=entity.get("creationDate") or "",
            gleif_entity_status=entity.get("status") or "",
            gleif_jurisdiction=entity.get("jurisdiction") or "",
            gleif_legal_form_code=(entity.get("legalForm") or {}).get("id") or "",
            gleif_registered_address=", ".join(
                (entity.get("legalAddress") or {}).get("addressLines", [])
            ),
            gleif_source_response_sha256=item["evidence"]["response_sha256"],
        )
    return result


def graphml(output, nodes, edges):
    """Groups stay hyperedges in sidecars; no invented pairwise ownership links."""
    fields = list(nodes[0])
    with (output / "enterprise-graph.graphml").open("w") as stream:
        stream.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        )
        for field in fields:
            stream.write(
                f'<key id={quoteattr(field)} for="node" '
                f'attr.name={quoteattr(field)} attr.type="string"/>\n'
            )
        for field in ("relation", "valid_from", "valid_to", "source_system", "source_row_sha256"):
            stream.write(
                f'<key id={quoteattr("edge_" + field)} for="edge" '
                f'attr.name={quoteattr(field)} attr.type="string"/>\n'
            )
        stream.write('<graph id="uk-research" edgedefault="directed">\n')
        for node in nodes:
            stream.write(f"<node id={quoteattr(node['id'])}>")
            for field, value in node.items():
                stream.write(f"<data key={quoteattr(field)}>{escape(str(value))}</data>")
            stream.write("</node>\n")
        for edge in edges:
            stream.write(
                f"<edge id={quoteattr(edge['id'])} source={quoteattr(edge['source'])} "
                f"target={quoteattr(edge['target'])}>"
            )
            for field in (
                "relation",
                "valid_from",
                "valid_to",
                "source_system",
                "source_row_sha256",
            ):
                stream.write(
                    f"<data key={quoteattr('edge_' + field)}>{escape(str(edge[field]))}</data>"
                )
            stream.write("</edge>\n")
        stream.write("</graph></graphml>\n")


def run(output, source):
    if output.exists():
        raise ValueError("Choose a new graph version; existing datasets are immutable")
    references = {row["company_id"]: row for row in read_csv(BASIC / "company-reference.csv")}
    companies = set(references)
    if len(companies) != 229907:
        raise ValueError("Unexpected research company universe")
    records = [
        dict(company_id=company, **item)
        for company, item in fetch_companies(companies, source / "api-cache")
    ]
    matches, ambiguous = unique_matches(records)
    root_leis = {item["record"]["id"] for item in matches.values()}
    rr_zip = download_relationships(source)
    rr_sha = sha(rr_zip)
    publication = json.loads((source / "golden-copy-publish.json").read_text())["data"]
    reference_date = publication["publish_date"][:10]
    by_child, statuses = defaultdict(list), Counter()
    rr_rows = 0
    for row, provenance in relationship_records(rr_zip):
        rr_rows += 1
        edge, reason = parent_relationship(row, reference_date)
        statuses[reason or "accepted_parent_record"] += 1
        if edge:
            edge.update(
                source_member=provenance["member"],
                source_record_number=provenance["record_number"],
                source_row_sha256=provenance["row_sha256"],
            )
            by_child[edge["source_lei"]].append(edge)
    if rr_rows != publication["rr"]["full_file"]["csv"]["record_count"]:
        raise ValueError("GLEIF relationship record count disagrees with publication")
    visited, selected = ancestors(root_leis, by_child)
    known = {item["record"]["id"]: item for item in records}
    parents = {
        item["record"]["id"]: item
        for item in fetch_leis(visited - set(known), source / "api-cache")
    }
    known.update(parents)
    output.mkdir(parents=True)
    write_json(
        output / "build-state.json", {"status": "building", "targetCompanies": len(companies)}
    )
    lei_to_node = {item["record"]["id"]: company for company, item in matches.items()}
    for lei in visited - root_leis:
        lei_to_node[lei] = "LEI:" + lei
    observations, names, links = defaultdict(list), {}, []
    for row in read_csv(BASIC / "features.csv"):
        company = row["company_id"]
        observations[company].append(row["sample_id"])
        if row["company_name"]:
            names[company] = row["company_name"]
        links.append(
            {
                "node_id": company,
                "sample_id": row["sample_id"],
                "company_id": company,
                "observation_date": row["observation_date"],
                "baseline_report_id": row["baseline_report_id"],
            }
        )
    nodes = [
        research_node(
            references[company], matches.get(company), observations[company], names.get(company, "")
        )
        for company in sorted(companies)
    ]
    node_fields = list(nodes[0])
    nodes.extend(
        parent_node(lei, known.get(lei), node_fields) for lei in sorted(visited - root_leis)
    )
    write_csv(output / "nodes.csv", nodes, node_fields)
    write_csv(output / "node-observations.csv", links, list(links[0]))
    edge_rows, quarantined = [], []
    grouped_edges = defaultdict(list)
    for edge in selected:
        grouped_edges[
            (lei_to_node[edge["source_lei"]], lei_to_node[edge["target_lei"]], edge["relation"])
        ].append(edge)
    for (child, parent, kind), evidence in sorted(grouped_edges.items()):
        if child == parent:
            quarantined.extend({**row, "reason": "coalesced_self_parent"} for row in evidence)
            continue
        # Conflicting current records must not be silently collapsed into one asserted edge.
        if len(evidence) != 1:
            quarantined.extend(
                {**row, "reason": "multiple_current_records_for_same_edge"} for row in evidence
            )
            continue
        row = evidence[0]
        edge_rows.append(
            {
                "id": stable_id([child, parent, kind]),
                "source": child,
                "target": parent,
                **row,
                "source_system": "GLEIF",
                "source_archive_sha256": rr_sha,
                "source_publish_date": publication["publish_date"],
                "historical_prediction_eligible": False,
            }
        )
    edge_fields = [
        "id",
        "source",
        "target",
        "source_lei",
        "target_lei",
        "relation",
        "reported_status",
        "registration_status",
        "valid_from",
        "valid_to",
        "registration_initial_date",
        "registration_last_update",
        "validation_sources",
        "validation_documents",
        "validation_reference",
        "source_member",
        "source_record_number",
        "source_row_sha256",
        "source_system",
        "source_archive_sha256",
        "source_publish_date",
        "historical_prediction_eligible",
    ]
    write_csv(output / "edges.csv", edge_rows, edge_fields)
    with gzip.open(output / "relationship-evidence.jsonl.gz", "wt") as stream:
        for row, provenance in relationship_records(rr_zip):
            if row["Relationship.StartNode.NodeID"] in visited:
                stream.write(json.dumps({"row": row, "evidence": provenance}) + "\n")
    with gzip.open(output / "gleif-entity-evidence.jsonl.gz", "wt") as stream:
        for lei in sorted(known):
            if lei in visited or registered_company(known[lei]["record"]) in companies:
                stream.write(json.dumps(known[lei]) + "\n")
    write_json(output / "quarantined-relations.json", quarantined)
    write_csv(
        output / "gleif-matches.csv",
        (
            {
                "company_id": company,
                "match_status": "unique"
                if company in matches
                else "ambiguous"
                if company in ambiguous
                else "no_usable_match",
                "lei": matches[company]["record"]["id"] if company in matches else "",
                "ambiguous_candidates": "|".join(ambiguous.get(company, [])),
            }
            for company in sorted(companies)
        ),
        ["company_id", "match_status", "lei", "ambiguous_candidates"],
    )
    addresses = defaultdict(list)
    with gzip.open(BASIC / "snapshot-raw-records.jsonl.gz", "rt") as stream:
        for line in stream:
            raw = json.loads(line)
            row = references[raw["company_id"]]
            row["snapshot_RegAddress.AddressLine1"] = raw["row"].get("RegAddress.AddressLine1", "")
            key = address_key(row)
            if key:
                # POBox disambiguates records otherwise sharing the same postal components.
                key = stable_id([key, raw["row"].get("RegAddress.POBox", "").strip().upper()])
                addresses[key].append(row["company_id"])
    groups, memberships = [], []
    for key, members in sorted(addresses.items()):
        if len(members) < 2:
            continue
        group_id = "ADDRESS:" + key
        groups.append(
            {
                "id": group_id,
                "kind": "shared_registered_address",
                "member_count": len(members),
                "source_system": "Companies House",
                "source_date": "2026-09-30",
                "source_sha256": json.loads((BASIC / "source-manifest.json").read_text())[
                    "snapshotSha256"
                ],
                "historical_prediction_eligible": False,
            }
        )
        memberships.extend({"group_id": group_id, "node_id": member} for member in sorted(members))
    group_fields = [
        "id",
        "kind",
        "member_count",
        "source_system",
        "source_date",
        "source_sha256",
        "historical_prediction_eligible",
    ]
    write_csv(output / "groups.csv", groups, group_fields)
    write_csv(output / "group-memberships.csv", memberships, ["group_id", "node_id"])
    graphml(output, nodes, edge_rows)
    for filename in (
        "features.csv",
        "labels.csv",
        "matches.csv",
        "excluded-cases.csv",
        "excluded-case-basic-information.csv",
        "company-reference.csv",
        "feature-contract.json",
        "coverage.json",
        "source-manifest.json",
        "historical-basic-profiles.jsonl.gz",
        "snapshot-raw-records.jsonl.gz",
    ):
        shutil.copyfile(BASIC / filename, output / filename)
    shutil.copyfile(EVENTS, output / "events.csv")
    write_csv(
        output / "event-node-links.csv",
        (
            {"node_id": row["company_id"], "event_id": row["event_id"]}
            for row in read_csv(EVENTS)
            if row["company_id"] in companies
        ),
        ["node_id", "event_id"],
    )
    isolated = (
        companies
        - {row[field] for row in edge_rows for field in ("source", "target")}
        - {row["node_id"] for row in memberships}
    )
    summary = {
        "researchCompanies": len(companies),
        "companyNodes": len(nodes),
        "addedParentNodes": len(nodes) - len(companies),
        "uniquelyMatchedResearchCompanies": len(matches),
        "ambiguousResearchCompanies": len(ambiguous),
        "parentRelationships": len(edge_rows),
        "relationsByType": Counter(row["relation"] for row in edge_rows),
        "addressGroups": len(groups),
        "addressMemberships": len(memberships),
        "isolatedResearchCompanies": len(isolated),
        "namesMissing": sum(row["name_missing"] for row in nodes),
        "observationRows": len(links),
        "missingParentBasicRecords": len((visited - root_leis) - set(known)),
        "sourceRelationshipRows": rr_rows,
        "sourceRelationshipSelection": statuses,
        "quarantinedRelations": len(quarantined),
    }
    write_json(output / "graph-summary.json", summary)
    write_json(
        output / "graph-manifest.json",
        {
            "format": "uk-research-graph-v1",
            "scope": "research_companies_and_accounting_parents",
            "graphDate": reference_date,
            "edgeDirection": "child_to_parent",
            "nodes": "nodes.csv",
            "edges": "edges.csv",
            "groups": "groups.csv",
            "memberships": "group-memberships.csv",
            "graphml": "enterprise-graph.graphml",
            "observationJoin": "node-observations.csv",
            "eventJoin": "event-node-links.csv",
            "historicalRelationshipsVerified": False,
            "containsTrainedModelOrPredictions": False,
            "relationshipSource": {
                "url": publication["rr"]["full_file"]["csv"]["url"],
                "publishDate": publication["publish_date"],
                "sha256": rr_sha,
            },
            "apiPublishDates": sorted(
                {item["evidence"]["publish_date"] for item in known.values()}
            ),
            "inputFiles": {
                str(path.relative_to(ROOT)): sha(path)
                for path in [
                    BASIC / "company-reference.csv",
                    BASIC / "features.csv",
                    BASIC / "labels.csv",
                    EVENTS,
                ]
            },
            "codeFiles": {
                str(path.relative_to(ROOT)): sha(path)
                for path in [
                    Path(__file__),
                    Path(__file__).parent / "uk_graph/core.py",
                    Path(__file__).parent / "uk_graph/gleif.py",
                ]
            },
        },
    )
    write_json(output / "build-state.json", {"status": "complete", **summary})
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--gleif-source", type=Path, default=SOURCE)
    args = parser.parse_args()
    run(args.output, args.gleif_source)
