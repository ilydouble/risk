"""Verify complete hyperedge membership, source evidence, preservation and GraphML."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree

from extend_uk_hyperedges import BASE, OUTPUT, key_for, raw_records
from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from uk_graph.gleif import stable_id
from uk_graph.hyperedges import KINDS, SOURCE_DATE, common_parent_facts, group_id, snapshot_facts


def validate(output=OUTPUT, base=BASE):
    manifest = json.loads((output / "hyperedge-manifest.json").read_text())
    assert sha(base / "validation.json") == manifest["baseValidationSha256"]
    assert json.loads((base / "validation.json").read_text())["passed"]
    for name, digest in manifest["preservedFiles"].items():
        assert sha(output / name) == digest == sha(base / name), name
    classification = output / "sources/classifications/sic-codes.csv"
    assert sha(classification) == manifest["classificationSha256"]
    sic_codes = {
        row["SIC Code"].strip(): row["Description"].strip() for row in read_csv(classification)
    }
    nodes = {row["id"]: row for row in read_csv(output / "nodes.csv")}
    research = {node for node, row in nodes.items() if row["is_research_company"] == "True"}
    assert len(research) == 229907
    group_list = list(read_csv(output / "groups.csv"))
    groups = {row["id"]: row for row in group_list}
    assert len(groups) == len(group_list) and set(groups).isdisjoint(nodes)
    members, by_group = set(), defaultdict(set)
    for row in read_csv(output / "group-memberships.csv"):
        pair = row["group_id"], row["node_id"]
        assert pair not in members and pair[0] in groups and pair[1] in nodes
        members.add(pair)
        by_group[pair[0]].add(pair[1])
    old_groups = {row["id"]: row for row in read_csv(base / "groups.csv")}
    old_members = {
        (row["group_id"], row["node_id"]) for row in read_csv(base / "group-memberships.csv")
    }
    assert old_members <= members
    assert {
        pair for pair in members if groups[pair[0]]["kind"] == "shared_registered_address"
    } == old_members
    for identity, old in old_groups.items():
        assert all(groups[identity][field] == value for field, value in old.items())
    expected = defaultdict(set)
    for _, record in raw_records(output / "snapshot-raw-records.jsonl.gz"):
        assert record["company_id"] in research
        for fact in snapshot_facts(record["row"], sic_codes):
            expected[key_for(fact)].add(record["company_id"])
    edges = list(read_csv(output / "edges.csv"))
    parent_facts = list(common_parent_facts(edges))
    for fact in parent_facts:
        expected[key_for(fact)].add(fact["node_id"])
    expected_ids = set()
    for (kind, value, date), companies in expected.items():
        identity = group_id(kind, value, date)
        if len(companies) < 2:
            assert identity not in groups
            continue
        assert identity in groups and by_group[identity] == companies
        assert groups[identity]["value"] == value and groups[identity]["source_date"] == date
        expected_ids.add(identity)
    assert set(groups) == set(old_groups) | expected_ids
    kinds, kind_memberships, coverage = Counter(), Counter(), defaultdict(set)
    for identity, group in groups.items():
        assert group["kind"] in KINDS
        assert int(group["member_count"]) == len(by_group[identity]) >= 2
        assert group["historical_prediction_eligible"] == "False"
        semantic, family, level, relation = KINDS[group["kind"]]
        assert (
            group["semantic_kind"],
            group["family"],
            group["level"],
            group["membership_relation"],
        ) == (semantic, family, level, relation)
        if group["parent_group_id"]:
            assert group["parent_group_id"] in groups
            assert by_group[identity] <= by_group[group["parent_group_id"]]
        if semantic == "attribute":
            assert group["source_date"] == SOURCE_DATE and by_group[identity] <= research
        if family == "industry":
            assert group["classification_sha256"] == manifest["classificationSha256"]
        kinds[group["kind"]] += 1
        kind_memberships[group["kind"]] += len(by_group[identity])
        coverage[group["kind"]].update(by_group[identity])
    source_iter = iter(raw_records(output / "snapshot-raw-records.jsonl.gz"))
    current_number, current = 0, None
    facts = {}
    seen_evidence = set()
    for evidence in read_csv(output / "membership-evidence.csv"):
        pair = evidence["group_id"], evidence["node_id"]
        assert pair in members and pair not in seen_evidence
        seen_evidence.add(pair)
        fields, values = (
            json.loads(evidence["source_fields"]),
            json.loads(evidence["source_values"]),
        )
        number = int(evidence["source_record_number"])
        group = groups[pair[0]]
        if evidence["source_file"] == "snapshot-raw-records.jsonl.gz":
            assert number >= current_number
            while current_number < number:
                current_number, current = next(source_iter)
                facts = {
                    (fact["kind"], fact["value"]): fact
                    for fact in snapshot_facts(current["row"], sic_codes)
                }
            assert current["company_id"] == pair[1] == evidence["source_record_id"]
            assert current["row_sha256"] == evidence["source_row_sha256"]
            assert [current["row"].get(field, "") for field in fields] == values
            if group["kind"] != "shared_registered_address":
                fact = facts[group["kind"], group["value"]]
                assert fields == fact["source_fields"] and values == fact["source_values"]
        else:
            assert evidence["source_file"] == "edges.csv"
            edge = edges[number - 2]
            assert edge["id"] == evidence["source_record_id"]
            assert stable_id(edge) == evidence["source_row_sha256"]
            assert [edge[field] for field in fields] == values
            assert edge["source"] == pair[1] and edge["target"] == group["value"]
    assert seen_evidence == members
    parent_ids = {edge["id"] for edge in edges}
    full = json.loads((output / "full-graph-export.json").read_text())
    assert sha(output / full["file"]) == full["sha256"]
    graph_nodes, graph_parent_edges, graph_members = set(), set(), set()
    namespace = "{http://graphml.graphdrawing.org/xmlns}"
    for _, element in ElementTree.iterparse(output / full["file"], events=("end",)):
        if element.tag == namespace + "node":
            identity = element.get("id")
            assert identity in nodes or identity in groups
            assert identity not in graph_nodes
            if identity in groups:
                label = element.find(namespace + "data[@key='name']").text
                assert label
                if groups[identity]["label"]:
                    assert label == groups[identity]["label"]
            graph_nodes.add(identity)
            element.clear()
        elif element.tag == namespace + "edge":
            identity = element.get("id")
            if identity.startswith("MEMBER:"):
                pair = element.get("target"), element.get("source")
                assert pair in members and pair not in graph_members
                relation = element.find(namespace + "data[@key='edge_relation']").text
                assert relation == groups[pair[0]]["membership_relation"]
                assert identity == "MEMBER:" + stable_id(list(pair))
                graph_members.add(pair)
            else:
                assert identity in parent_ids and identity not in graph_parent_edges
                graph_parent_edges.add(identity)
            element.clear()
    assert graph_nodes == set(nodes) | set(groups)
    assert graph_members == members and graph_parent_edges == parent_ids
    summary = json.loads((output / "graph-summary.json").read_text())
    assert summary["hyperedgesByType"] == kinds and summary["membershipsByType"] == kind_memberships
    assert summary["hyperedges"] == len(groups) and summary["hyperedgeMemberships"] == len(members)
    connected = {node for _, node in members} | {
        edge[field] for edge in edges for field in ("source", "target")
    }
    assert len(research - connected) == summary["isolatedResearchCompanies"]
    result = {
        "passed": True,
        "researchCompaniesPreserved": len(research),
        "companyNodes": len(nodes),
        "ordinaryParentEdgesPreserved": len(edges),
        "hyperedges": len(groups),
        "memberships": len(members),
        "types": kinds,
        "allMembershipsHaveVerifiedEvidence": True,
        "fullGraphmlVerified": True,
        "financialLabelsEventsAndBaseEntitiesUnchanged": True,
        "sourceSnapshotOnlyForAttributeHyperedges": True,
        "historicalPredictionEligibilityNotAsserted": True,
    }
    write_json(output / "validation.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--base", type=Path, default=BASE)
    args = parser.parse_args()
    validate(args.output, args.base)
