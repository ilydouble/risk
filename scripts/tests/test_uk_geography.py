"""Stable contracts for exact administrative joins and intersection hyperedges."""

from extend_uk_geography import geography_record, observation_geography
from fetch_uk_postcode_geography import batch
from uk_graph.geography import (
    administrative_facts,
    canonical_postcode,
    crossed_facts,
    lifecycle_compatible,
)


def test_canonical_postcodes_and_no_fuzzy_matching():
    assert canonical_postcode(" nr21ad ") == "NR2 1AD"
    assert canonical_postcode("ＧＩＲ０ＡＡ") == "GIR 0AA"
    assert canonical_postcode("UNKNOWN") == ""
    assert canonical_postcode("NR2") == ""


def test_regions_sentinels_and_unknown_admin_codes_are_not_groups():
    facts = administrative_facts(
        {"lad26cd": "W06000015", "rgn26cd": "W99999999"},
        {"W06000015": "Cardiff", "W99999999": "(pseudo) Wales"},
    )
    assert len(facts) == 1
    assert facts[0]["value"] == "W06000015"
    assert administrative_facts({"lad26cd": "E00000000"}, {}) == []


def test_multiple_industries_cross_each_admin_dimension_only():
    industries = [
        {"kind": "industry_sic_subclass", "value": "62012", "label": "Software"},
        {"kind": "industry_sic_division", "value": "62", "label": "Computing"},
        {"kind": "legal_form", "value": "LTD", "label": "Limited"},
    ]
    geo = administrative_facts(
        {"lad26cd": "E07000148", "rgn26cd": "E12000006"},
        {"E07000148": "Norwich", "E12000006": "East of England"},
    )
    facts = list(crossed_facts(industries, geo))
    assert len(facts) == 4
    assert {f["value"] for f in facts} == {
        "62012|E07000148",
        "62012|E12000006",
        "62|E07000148",
        "62|E12000006",
    }
    assert all(len(f["components"]) == 2 for f in facts)


def test_lifecycle_rejects_future_and_terminated_postcodes():
    assert not lifecycle_compatible({"dointr": 202001}, "2019-12-31")
    assert not lifecycle_compatible({"dointr": 198001, "doterm": 201811}, "2019-01-31")
    assert lifecycle_compatible({"dointr": 198001, "doterm": 201901}, "2019-01-31")
    assert not lifecycle_compatible({"dointr": None}, "2019-01-31")


def test_ambiguous_postcode_never_arbitrarily_joined():
    assert geography_record("NR2 1AD", {"NR2 1AD": {"status": "ambiguous"}}) is None


def test_truncated_public_response_is_paginated_and_frozen(tmp_path, monkeypatch):
    offsets = []

    def response(url, params):
        offsets.append(params["resultOffset"])
        return {
            "features": [{"attributes": {"ObjectId": len(offsets)}}],
            "exceededTransferLimit": len(offsets) == 1,
        }

    monkeypatch.setattr("fetch_uk_postcode_geography.request_json", response)
    path, cached = batch(["NR2 1AD"], tmp_path, {"dataLastEditDate": 1})
    assert offsets == [0, 1]
    assert len(cached["pages"]) == 2
    assert cached["requestedPostcodes"] == ["NR2 1AD"]
    assert batch(["NR2 1AD"], tmp_path, {"dataLastEditDate": 1}) == (path, cached)
    assert offsets == [0, 1]


def test_observation_mapping_separates_report_address_and_current_assumption():
    ref = {
        "attributes": {"pcds": "NR2 1AD", "dointr": 198001, "lad26cd": "E07000148", "ObjectId": 1},
        "sourceFile": "raw/example.json.gz",
        "attributesSha256": "digest",
    }
    lookup = {"NR2 1AD": {"status": "matched", "candidates": [ref]}}
    row = {
        "sample_id": "sample",
        "company_id": "company",
        "observation_date": "2019-01-31",
        "historical_registered_office_postcode": "NR2 1AD",
        "historical_basic_available_by_assumed": "2018-05-31",
    }
    mapped = observation_geography(row, "", lookup, {"E07000148": "Norwich"})
    assert mapped["mapping_basis"] == "historical_financial_report_postcode"
    assert not mapped["historical_address_verified"]
    assert mapped["fixed_2026_boundary_projection_applied"]
    row["historical_basic_available_by_assumed"] = "2020-01-31"
    future = observation_geography(row, "", lookup, {"E07000148": "Norwich"})
    assert future["mapping_basis"] == "unmapped"
    assert not future["historical_postcode_available_by_observation_assumed"]
    row["historical_registered_office_postcode"] = ""
    fallback = observation_geography(row, "NR2 1AD", lookup, {"E07000148": "Norwich"})
    assert fallback["current_registry_assumption_applied"]
    assert fallback["mapping_basis"] == "current_registry_assumption"
    assert observation_geography(row, "", lookup, {})["mapping_basis"] == "unmapped"
