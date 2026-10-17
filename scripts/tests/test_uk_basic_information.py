"""Historical entity facts must retain context, identity and time boundaries."""

import sys
from html import escape
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_uk_basic_information import historical, reference  # noqa: E402
from prepare_uk_basic_references import FIELDS as EVENT_FIELDS  # noqa: E402
from prepare_uk_basic_references import event_reference  # noqa: E402
from uk_financials.basic import age_days, parse_basic_document  # noqa: E402


def document(facts, contexts=""):
    return f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
    xmlns:x="http://www.xbrl.org/2003/instance" xmlns:d="http://xbrl.org/2006/xbrldi"
    xmlns:b="http://xbrl.frc.org.uk/core" xmlns:c="http://xbrl.frc.org.uk/countries">
    <x:context id="now"><x:period><x:instant>2020-12-31</x:instant></x:period></x:context>
    <x:context id="later"><x:period><x:instant>2021-12-31</x:instant></x:period></x:context>
    {contexts}{facts}</html>""".encode()


def fact(concept, value="", context="now"):
    return f'<ix:nonNumeric name="b:{concept}" contextRef="{context}">{value}</ix:nonNumeric>'


def dimensional_context(identifier, axis, member):
    return f'''<x:context id="{identifier}"><x:entity><x:segment>
    <d:explicitMember dimension="b:{axis}">b:{member}</d:explicitMember>
    </x:segment></x:entity><x:period><x:instant>2020-12-31</x:instant></x:period></x:context>'''


def test_empty_text_dimensions_are_facts_and_false_is_observed():
    raw = document(
        fact("LegalFormEntity", context="legal")
        + fact("CountryFormationOrIncorporation", context="country")
        + fact("EntityDormantTruefalse", "false"),
        dimensional_context("legal", "LegalFormEntityDimension", "PrivateLimitedCompanyLtd")
        + dimensional_context("country", "CountriesRegionsDimension", "Scotland"),
    )
    profile = parse_basic_document(raw, "00012345", "2020-12-31")
    assert profile["values"] == {
        "legal_form": "PrivateLimitedCompanyLtd",
        "country_of_incorporation": "GB",
        "dormant": False,
    }
    result = historical(
        {
            **profile,
            "report_id": "r",
            "period_end": "2020-12-31",
            "availability_upper_bound": "2021-01-31",
        },
        "2021-02-28",
    )
    assert result["historical_dormant_missing"] is False
    assert result["historical_registry_status_missing"] is True
    assert profile["facts"]["country_of_incorporation"]["jurisdiction"] == "scotland"


@pytest.mark.parametrize(
    "value,code,status",
    [
        ("AllCountries", "", "aggregate_or_unknown"),
        ("{PLACE OF INCORPORATION}", "", "template_placeholder"),
        ("England & Wales", "GB", "normalized"),
        (
            "Acme Ltd is a private limited company incorporated in Scotland.",
            "GB",
            "normalized_explicit_description",
        ),
        ("Unrecognized country", "", "unknown"),
    ],
)
def test_country_normalization_preserves_raw_without_inference(value, code, status):
    from uk_financials.countries import normalize_country

    normalized = normalize_country(value)
    assert normalized["code"] == code and normalized["status"] == status
    profile = parse_basic_document(
        document(fact("CountryFormationOrIncorporation", escape(value))), "00012345", "2020-12-31"
    )
    assert profile["values"].get("country_of_incorporation", "") == code
    assert profile["country_normalizations"][0]["raw_value"] == value


def test_registered_office_requires_contact_dimension():
    contexts = dimensional_context(
        "office", "EntityContactTypeDimension", "RegisteredOffice"
    ) + dimensional_context("agent", "EntityContactTypeDimension", "Accountant")
    raw = document(
        fact("PostalCodeZip", "AB1 2CD", "office")
        + fact("PostalCodeZip", "ZZ9 9ZZ", "agent")
        + fact("AddressLine1", "Unqualified address"),
        contexts,
    )
    values = parse_basic_document(raw, "00012345", "2020-12-31")["values"]
    assert values == {"registered_office_postcode": "AB1 2CD"}


def test_future_context_conflicts_and_wrong_identity_are_rejected():
    raw = document(fact("EntityName", "Past") + fact("EntityName", "Future", "later"))
    assert (
        parse_basic_document(raw, "00012345", "2020-12-31")["values"]["registered_name"] == "Past"
    )
    raw = document(fact("EntityDormantTruefalse", "true") + fact("EntityDormantTruefalse", "false"))
    profile = parse_basic_document(raw, "00012345", "2020-12-31")
    assert profile["values"] == {} and profile["conflicts"] == ["dormant"]
    with pytest.raises(ValueError, match="identity"):
        parse_basic_document(
            document(fact("UKCompaniesHouseRegisteredNumber", "00099999")), "00012345", "2020-12-31"
        )


def test_snapshot_is_reference_only_and_cannot_fill_historical_features():
    ref = reference(
        "00012345",
        {
            "00012345": {
                "row": {
                    "CompanyName": "Now",
                    "CompanyStatus": "Active",
                    "IncorporationDate": "01/01/2000",
                }
            }
        },
    )
    assert ref["snapshot_IncorporationDate"] == "2000-01-01"
    history = historical(None, "2020-12-31")
    assert history["historical_incorporation_date_missing"] is True
    assert history["historical_registry_status"] == ""
    assert age_days("2020-12-31", "2021-01-01") == ""
    with pytest.raises(ValueError, match="Future"):
        historical(
            {"period_end": "2020-12-31", "availability_upper_bound": "2021-02-01"}, "2021-01-31"
        )


def test_event_reference_preserves_time_and_sic_leading_zero():
    early = dict.fromkeys(EVENT_FIELDS, "")
    early.update(event_id="a", reference_month="2021-02", sic07_5_digit="1110")
    later = {**early, "event_id": "b", "reference_month": "2022-02", "sic07_5_digit": "99999"}
    result = event_reference([later, early])
    assert result["event_reference_sic07_5_digit"] == "01110"
    assert result["event_reference_reference_month"] == "2021-02"
    assert result["event_reference_baseline_availability_verified"] is False
    assert all(key.startswith("event_reference_") for key in result)
    missing = event_reference([{**early, "sic07_5_digit": "NA"}])
    assert missing["event_reference_sic07_5_digit"] == ""
