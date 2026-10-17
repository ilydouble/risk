"""Stable identity, relationship, time and graph serialization contracts."""

import sys
from pathlib import Path
from xml.etree import ElementTree

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from finalize_uk_graph import group_view  # noqa: E402
from prepare_uk_graph import graphml  # noqa: E402
from uk_graph.core import address_key, ancestors, parent_relationship, unique_matches  # noqa: E402
from uk_graph.gleif import (  # noqa: E402
    company_number,
    query,
    records_from_query,
    registered_company,
)


def entity(lei="A", company="00012345", authority="RA000585", status="ISSUED"):
    return {
        "company_id": company,
        "record": {
            "id": lei,
            "attributes": {
                "entity": {"registeredAt": {"id": authority}, "registeredAs": company},
                "registration": {"status": status},
            },
        },
    }


def relationship():
    return {
        "Relationship.RelationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
        "Relationship.StartNode.NodeID": "213800LBQA1Y9L22JB70",
        "Relationship.EndNode.NodeID": "5493001Z012YSB2A0K51",
        "Relationship.StartNode.NodeIDType": "LEI",
        "Relationship.EndNode.NodeIDType": "LEI",
        "Relationship.RelationshipStatus": "ACTIVE",
        "Registration.RegistrationStatus": "LAPSED",
        "Registration.InitialRegistrationDate": "2020-01-01",
        "Registration.LastUpdateDate": "2025-01-01",
        "Registration.ValidationSources": "ENTITY_SUPPLIED_ONLY",
        "Registration.ValidationDocuments": "ACCOUNTS_FILING",
        "Registration.ValidationReference": "https://example.org/evidence",
    }


def test_only_correct_registry_identifiers_match_not_names_or_foreign_numbers():
    assert company_number("12345") == "00012345"
    assert company_number("sc123456") == "SC123456"
    assert company_number("123/45") == ""
    assert registered_company(entity()["record"]) == "00012345"
    assert registered_company(entity(authority="RA000602")["record"]) == ""


def test_duplicate_and_ambiguous_lei_mappings_are_not_arbitrarily_chosen():
    valid = entity()
    matches, ambiguous = unique_matches([valid, entity("B", status="DUPLICATE")])
    assert matches["00012345"] == valid and not ambiguous
    matches, ambiguous = unique_matches([valid, entity("C")])
    assert not matches and ambiguous["00012345"] == ["A", "C"]


def test_relationship_period_is_not_accounting_period_and_lapsed_is_explicit():
    row = relationship()
    row.update(
        {
            "Relationship.Period.1.periodType": "ACCOUNTING_PERIOD",
            "Relationship.Period.1.startDate": "2020-01-01",
            "Relationship.Period.1.endDate": "2020-12-31",
            "Relationship.Period.2.periodType": "RELATIONSHIP_PERIOD",
            "Relationship.Period.2.startDate": "2010-01-01",
            "Relationship.Period.2.endDate": "",
        }
    )
    edge, reason = parent_relationship(row, "2026-10-17")
    assert not reason and edge["valid_from"] == "2010-01-01"
    assert edge["valid_to"] == "" and edge["registration_status"] == "LAPSED"
    assert edge["source_lei"] == row["Relationship.StartNode.NodeID"]


@pytest.mark.parametrize(
    "updates,reason",
    [
        ({"Relationship.RelationshipType": "IS_FUND-MANAGED_BY"}, "other_relationship_type"),
        ({"Relationship.RelationshipStatus": "INACTIVE"}, "not_reported_active"),
        ({"Relationship.EndNode.NodeID": "213800LBQA1Y9L22JB70"}, "self_parent"),
        (
            {
                "Relationship.Period.1.periodType": "RELATIONSHIP_PERIOD",
                "Relationship.Period.1.endDate": "2024-12-31",
            },
            "outside_reported_relationship_period",
        ),
    ],
)
def test_non_parent_inactive_self_and_ended_relationships_are_not_asserted(updates, reason):
    assert parent_relationship({**relationship(), **updates}, "2026-10-17") == (None, reason)


def test_ancestor_closure_adds_parents_but_not_unrelated_children_and_terminates_cycles():
    first = {"source_lei": "child", "target_lei": "parent"}
    second = {"source_lei": "parent", "target_lei": "ultimate"}
    cycle = {"source_lei": "ultimate", "target_lei": "parent"}
    seen, edges = ancestors(
        {"child"}, {"child": [first], "parent": [second], "ultimate": [cycle], "other": [first]}
    )
    assert seen == {"child", "parent", "ultimate"} and edges == [first, second, cycle]


def test_same_postcode_is_insufficient_for_shared_registered_address():
    row = {
        "snapshot_missing": "False",
        "snapshot_RegAddress.AddressLine1": "  10 MAIN street ",
        "snapshot_RegAddress.PostCode": "AB1 2CD",
    }
    assert address_key(row) == address_key(
        {**row, "snapshot_RegAddress.AddressLine1": "10 Main Street"}
    )
    assert address_key(row) != address_key(
        {**row, "snapshot_RegAddress.AddressLine1": "20 Main Street"}
    )
    assert not address_key({**row, "snapshot_missing": "True"})


def test_paginated_raw_responses_are_complete_and_cached(tmp_path, monkeypatch):
    calls = []

    def handle(request):
        page = int(request.url.params["page[number]"])
        calls.append(page)
        return httpx.Response(
            200,
            json={
                "data": [{"id": str(page)}],
                "meta": {
                    "pagination": {"currentPage": page, "lastPage": 2, "total": 2},
                    "goldenCopy": {"publishDate": "2026-10-17T00:00:00Z"},
                },
            },
        )

    client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs)
    )
    result = query({"filter[lei]": "A,B"}, tmp_path)
    assert [item["record"]["id"] for item in records_from_query(result)] == ["1", "2"]
    assert query({"filter[lei]": "A,B"}, tmp_path) == result and calls == [1, 2]


def test_graphml_preserves_ids_direction_and_escaped_names(tmp_path):
    nodes = [{"id": "00012345", "name": "A & B <Ltd>"}, {"id": "LEI:parent", "name": "Parent"}]
    edge = {
        "id": "r",
        "source": "00012345",
        "target": "LEI:parent",
        "relation": "IS_DIRECTLY_CONSOLIDATED_BY",
        "valid_from": "",
        "valid_to": "",
        "source_system": "GLEIF",
        "source_row_sha256": "a" * 64,
    }
    graphml(tmp_path, nodes, [edge])
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    root = ElementTree.parse(tmp_path / "enterprise-graph.graphml").getroot()
    assert root.find("g:graph/g:node/g:data[@key='name']", ns).text == "A & B <Ltd>"
    assert root.find("g:graph/g:edge", ns).get("source") == "00012345"


def test_full_graph_represents_groups_without_pairwise_company_edges():
    nodes = [
        {"id": company, "snapshot_registered_address": "10 Main Street"}
        for company in ("00000001", "00000002")
    ]
    groups = [{"id": "ADDRESS:a", "source_date": "2026-09-30"}]
    memberships = [{"group_id": "ADDRESS:a", "node_id": node["id"]} for node in nodes]
    group_nodes, edges = group_view(nodes, groups, memberships)
    assert len(group_nodes) == 1 and len(edges) == 2
    assert {edge["source"] for edge in edges} == {node["id"] for node in nodes}
    assert all(edge["target"] == "ADDRESS:a" for edge in edges)
    assert all(edge["relation"] == "MEMBER_OF_REGISTERED_ADDRESS_GROUP" for edge in edges)
