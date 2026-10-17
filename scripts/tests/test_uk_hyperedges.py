"""Industry, postal and parent grouping contracts; no unknown or outcome groups."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from finalize_uk_graph import group_view  # noqa: E402
from uk_graph.hyperedges import (  # noqa: E402
    common_parent_facts,
    group_id,
    postal_units,
    snapshot_facts,
)


def test_multiple_sic_codes_keep_distinct_subclasses_and_one_division_membership():
    row = {
        "SICCode.SicText_1": "01110 - Growing cereals",
        "SICCode.SicText_2": "01120 - Growing rice",
        "SICCode.SicText_3": "01110 - Growing cereals",
    }
    facts = snapshot_facts(row, {"01110": "Cereals", "01120": "Rice"})
    divisions = [f for f in facts if f["kind"] == "industry_sic_division"]
    subclasses = [f for f in facts if f["kind"] == "industry_sic_subclass"]
    assert len(divisions) == 1 and divisions[0]["value"] == "01"
    assert {f["value"] for f in subclasses} == {"01110", "01120"}
    assert len(divisions[0]["source_fields"]) == 3
    assert all(f["parent_group_id"] == group_id("industry_sic_division", "01") for f in subclasses)


def test_missing_pseudo_unknown_and_event_industry_do_not_form_industry_groups():
    row = {
        "SICCode.SicText_1": "99999 - Dormant Company",
        "SICCode.SicText_2": "74990 - Non-trading company",
        "SICCode.SicText_3": "NA",
        "SICCode.SicText_4": "12345 - Unknown",
        "event_reference_sic07_5_digit": "01110",
    }
    assert (
        snapshot_facts(row, {"99999": "Dormant", "74990": "Non-trading", "01110": "Cereals"}) == []
    )


@pytest.mark.parametrize(
    "postcode,expected",
    [
        (" sw1a 1aa ", ("SW", "SW1A")),
        ("EC1A1BB", ("EC", "EC1A")),
        ("M1 1AE", ("M", "M1")),
        ("BT7 1NN", ("BT", "BT7")),
        ("UNKNOWN", None),
        ("", None),
        ("BFPO 123", None),
    ],
)
def test_postal_area_and_district_are_parsed_without_claiming_administrative_geocoding(
    postcode, expected
):
    assert postal_units(postcode) == expected


def test_post_town_is_scoped_to_postal_area_and_missing_postcodes_do_not_mix():
    first = snapshot_facts(
        {"RegAddress.PostTown": "Newport", "RegAddress.PostCode": "NP20 1AA"}, {}
    )
    second = snapshot_facts(
        {"RegAddress.PostTown": "NEWPORT", "RegAddress.PostCode": "PO30 1AA"}, {}
    )
    first_town = next(f for f in first if f["kind"] == "registered_post_town")
    second_town = next(f for f in second if f["kind"] == "registered_post_town")
    assert first_town["value"] != second_town["value"]
    assert not snapshot_facts({"RegAddress.PostTown": "Newport"}, {})


def test_common_parent_facts_group_children_not_the_parent_itself():
    edges = [
        {
            "id": "r1",
            "source": "child",
            "target": "parent",
            "relation": "IS_DIRECTLY_CONSOLIDATED_BY",
            "source_publish_date": "2026-10-17",
            "source_archive_sha256": "a" * 64,
        }
    ]
    facts = list(common_parent_facts(edges))
    assert facts[0]["kind"] == "common_direct_parent" and facts[0]["node_id"] == "child"
    assert facts[0]["value"] == "parent"


def test_generic_group_view_preserves_type_label_and_membership_semantics():
    nodes = [{"id": "00012345", "snapshot_registered_address": "Address"}]
    groups = [
        {
            "id": "SIC:01",
            "kind": "industry_sic_division",
            "label": "SIC division 01",
            "source_date": "2026-09-30",
            "source_system": "Companies House",
            "membership_relation": "MEMBER_OF_INDUSTRY_SIC_DIVISION",
        }
    ]
    group_nodes, edges = group_view(nodes, groups, [{"group_id": "SIC:01", "node_id": "00012345"}])
    assert group_nodes[0]["name"] == "SIC division 01"
    assert group_nodes[0]["kind"] == "industry_sic_division_group"
    assert edges[0]["relation"] == "MEMBER_OF_INDUSTRY_SIC_DIVISION"
