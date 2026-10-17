"""Audit complete graph joins against the unchanged rebuilt cohort and raw sources."""

import gzip
import json
import unicodedata
from collections import Counter
from xml.etree import ElementTree

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from prepare_uk_graph import BASIC, EVENTS, OUTPUT, SOURCE, relationship_records
from uk_graph.gleif import AUTHORITIES, company_number


def validate(output=OUTPUT, source=SOURCE):
    manifest = json.loads((output / "graph-manifest.json").read_text())
    summary = json.loads((output / "graph-summary.json").read_text())
    originals = {row["company_id"] for row in read_csv(BASIC / "company-reference.csv")}
    nodes = {row["id"]: row for row in read_csv(output / "nodes.csv")}
    assert len(nodes) == sum(1 for _ in read_csv(output / "nodes.csv"))
    assert {
        node for node, row in nodes.items() if row["is_research_company"] == "True"
    } == originals
    assert len(originals) == 229907 and len(nodes) == summary["companyNodes"]
    assert not any("label" in row for row in nodes.values())
    lei_nodes = {row["lei"]: node for node, row in nodes.items() if row["lei"]}
    assert len(lei_nodes) == sum(bool(row["lei"]) for row in nodes.values())
    matched = set()
    for row in read_csv(output / "gleif-matches.csv"):
        assert row["company_id"] in originals
        if row["match_status"] == "unique":
            assert nodes[row["company_id"]]["lei"] == row["lei"]
            matched.add(row["company_id"])
        else:
            assert not nodes[row["company_id"]]["lei"]
    assert len(matched) == summary["uniquelyMatchedResearchCompanies"]
    verified = set()
    with gzip.open(output / "gleif-entity-evidence.jsonl.gz", "rt") as stream:
        for line in stream:
            item = json.loads(line)
            record = item["record"]
            if record["id"] not in lei_nodes:
                continue
            node_id = lei_nodes[record["id"]]
            entity = record["attributes"]["entity"]
            if node_id in originals:
                assert (entity.get("registeredAt") or {}).get("id") in AUTHORITIES
                assert company_number(entity["registeredAs"]) == node_id
            assert (
                nodes[node_id]["gleif_source_response_sha256"]
                == item["evidence"]["response_sha256"]
            )
            verified.add(record["id"])
    assert {nodes[node]["lei"] for node in matched} <= verified
    edges = list(read_csv(output / "edges.csv"))
    expected = {int(row["source_record_number"]): row for row in edges}
    assert len(expected) == len(edges)
    rr = source / "golden-relationships.csv.zip"
    rr_sha = sha(rr)
    assert rr_sha == manifest["relationshipSource"]["sha256"]
    verified_edges = set()
    for raw, evidence in relationship_records(rr):
        edge = expected.get(evidence["record_number"])
        if not edge:
            continue
        assert evidence["row_sha256"] == edge["source_row_sha256"]
        assert edge["source_member"] == evidence["member"]
        assert edge["source_lei"] == raw["Relationship.StartNode.NodeID"]
        assert edge["target_lei"] == raw["Relationship.EndNode.NodeID"]
        assert nodes[edge["source"]]["lei"] == edge["source_lei"]
        assert nodes[edge["target"]]["lei"] == edge["target_lei"]
        assert edge["source"] != edge["target"]
        assert edge["relation"] in {"IS_DIRECTLY_CONSOLIDATED_BY", "IS_ULTIMATELY_CONSOLIDATED_BY"}
        assert edge["relation"] == raw["Relationship.RelationshipType"]
        assert raw["Relationship.RelationshipStatus"] == "ACTIVE"
        assert edge["registration_status"] in {"PUBLISHED", "LAPSED"}
        assert edge["historical_prediction_eligible"] == "False"
        assert edge["source_archive_sha256"] == rr_sha
        for number in range(1, 6):
            if raw.get(f"Relationship.Period.{number}.periodType") != "RELATIONSHIP_PERIOD":
                continue
            start, end = (
                raw[f"Relationship.Period.{number}.startDate"],
                raw[f"Relationship.Period.{number}.endDate"],
            )
            assert edge["valid_from"] == start and edge["valid_to"] == end
            assert not start or start[:10] <= manifest["graphDate"]
            assert not end or end[:10] >= manifest["graphDate"]
        verified_edges.add(edge["id"])
    assert len(verified_edges) == len(edges) == summary["parentRelationships"]
    assert len({(row["source"], row["target"], row["relation"]) for row in edges}) == len(edges)
    groups = {row["id"]: row for row in read_csv(output / "groups.csv")}
    members = set()
    by_group = Counter()
    for row in read_csv(output / "group-memberships.csv"):
        key = row["group_id"], row["node_id"]
        assert key not in members and row["group_id"] in groups and row["node_id"] in originals
        members.add(key)
        by_group[row["group_id"]] += 1
    for key, group in groups.items():
        assert group["kind"] == "shared_registered_address"
        assert by_group[key] == int(group["member_count"]) >= 2
        assert group["historical_prediction_eligible"] == "False"
    assert len(groups) == summary["addressGroups"] and len(members) == summary["addressMemberships"]
    member_nodes = {node for _, node in members}
    assert len(member_nodes) == len(members)
    addresses = {}
    with gzip.open(output / "snapshot-raw-records.jsonl.gz", "rt") as stream:
        for line in stream:
            record = json.loads(line)
            if record["company_id"] in member_nodes:
                addresses[record["company_id"]] = tuple(
                    " ".join(
                        unicodedata.normalize("NFKC", record["row"].get("RegAddress." + field, ""))
                        .upper()
                        .split()
                    )
                    for field in (
                        "AddressLine1",
                        "AddressLine2",
                        "PostTown",
                        "County",
                        "Country",
                        "PostCode",
                        "POBox",
                    )
                )
    group_addresses = {}
    for group, node in members:
        value = addresses[node]
        assert value[0] and value[5]
        assert group_addresses.setdefault(group, value) == value
    for filename in (
        "features.csv",
        "labels.csv",
        "matches.csv",
        "excluded-cases.csv",
        "company-reference.csv",
        "excluded-case-basic-information.csv",
        "feature-contract.json",
        "historical-basic-profiles.jsonl.gz",
    ):
        assert sha(output / filename) == sha(BASIC / filename), filename
    observations = {row["sample_id"]: row for row in read_csv(output / "node-observations.csv")}
    count = 0
    for row in read_csv(output / "features.csv"):
        link = observations[row["sample_id"]]
        assert row["company_id"] == link["node_id"] == link["company_id"]
        assert row["observation_date"] == link["observation_date"]
        assert row["baseline_report_id"] == link["baseline_report_id"]
        assert link["node_id"] in originals
        count += 1
    assert count == len(observations) == summary["observationRows"] == 209192
    assert sha(output / "events.csv") == sha(EVENTS)
    event_links = {
        row["event_id"]: row["node_id"] for row in read_csv(output / "event-node-links.csv")
    }
    event_count = 0
    for row in read_csv(EVENTS):
        if row["company_id"] in originals:
            assert event_links[row["event_id"]] == row["company_id"]
            event_count += 1
    assert len(event_links) == event_count
    graphml_nodes, graphml_edges = set(), set()
    for _, element in ElementTree.iterparse(output / "enterprise-graph.graphml", events=("end",)):
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "node":
            assert element.get("id") in nodes and element.get("id") not in graphml_nodes
            graphml_nodes.add(element.get("id"))
            element.clear()
        elif kind == "edge":
            assert element.get("id") in verified_edges and element.get("id") not in graphml_edges
            assert element.get("source") in nodes and element.get("target") in nodes
            graphml_edges.add(element.get("id"))
            element.clear()
    assert graphml_nodes == set(nodes) and graphml_edges == verified_edges
    full_export = json.loads((output / "full-graph-export.json").read_text())
    assert sha(output / full_export["file"]) == full_export["sha256"]
    full_nodes, full_edges, full_members = set(), set(), set()
    for _, element in ElementTree.iterparse(output / full_export["file"], events=("end",)):
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "node":
            identity = element.get("id")
            assert identity in nodes or identity in groups
            assert identity not in full_nodes
            full_nodes.add(identity)
            element.clear()
        elif kind == "edge":
            identity = element.get("id")
            assert identity not in full_edges
            full_edges.add(identity)
            if identity.startswith("MEMBER:"):
                pair = element.get("target"), element.get("source")
                assert pair in members and pair not in full_members
                full_members.add(pair)
            else:
                assert identity in verified_edges
            element.clear()
    assert full_nodes == set(nodes) | set(groups)
    assert full_members == members
    assert len(full_edges) == len(members) + len(verified_edges)
    outside = {row["event_id"] for row in read_csv(output / "out-of-scope-events.csv")}
    assert outside.isdisjoint(event_links)
    assert outside | set(event_links) == {row["event_id"] for row in read_csv(EVENTS)}
    connected = {row[field] for row in edges for field in ("source", "target")} | {
        node for _, node in members
    }
    assert len(originals - connected) == summary["isolatedResearchCompanies"]
    result = {
        "passed": True,
        "researchCompaniesPreserved": len(originals),
        "companyNodes": len(nodes),
        "verifiedParentEdges": len(edges),
        "verifiedAddressGroups": len(groups),
        "verifiedMemberships": len(members),
        "financialObservationsPreserved": count,
        "eventLinksVerified": event_count,
        "sourceEventsOutsideResearchUniverseRetained": len(outside),
        "excludedCasesPreserved": sum(1 for _ in read_csv(output / "excluded-cases.csv")),
        "graphmlRoundtripVerified": True,
        "fullGraphmlGroupMembershipVerified": True,
        "historicalLabelsAndFinancialValuesUnchanged": True,
        "currentGraphNotDeclaredHistoricalTrainingData": True,
    }
    write_json(output / "validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    validate()
