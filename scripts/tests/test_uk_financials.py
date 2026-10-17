"""Financial retrieval and point-in-time fact extraction boundaries."""

import csv
import importlib.util
import io
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from uk_financials import archives  # noqa: E402
from uk_financials.facts import amount, parse_document  # noqa: E402

spec = importlib.util.spec_from_file_location("financials", SCRIPTS / "prepare_uk_financials.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def document(facts, extra_context=""):
    return f"""<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:x="http://www.xbrl.org/2003/instance"
      xmlns:d="http://xbrl.org/2006/xbrldi"
      xmlns:core="http://xbrl.frc.org.uk/fr/2023-01-01/core">
      <x:context id="current"><x:entity/>
      <x:period><x:instant>2023-12-31</x:instant></x:period></x:context>
      <x:context id="old"><x:entity/>
      <x:period><x:instant>2022-12-31</x:instant></x:period></x:context>
      {extra_context}
      <x:unit id="GBP"><x:measure>iso4217:GBP</x:measure></x:unit>
      <ix:nonNumeric name="core:UKCompaniesHouseRegisteredNumber">00012345</ix:nonNumeric>
      {facts}</html>""".encode()


@pytest.mark.parametrize(
    "value,form,scale,sign,expected",
    [
        ("1,234", "ixt:numdotdecimal", "3", "", "1.234E+6"),
        ("1.234,50", "ixt:numcommadecimal", "0", "-", "-1234.5"),
        ("-", "ixt:zerodash", "0", "", "0"),
        ("1.234,50", "ixt:unknown", "0", "", None),
        ("NaN", "", "0", "", None),
    ],
)
def test_amount_transformations(value, form, scale, sign, expected):
    assert amount(value, form, scale, sign) == expected


def test_comparatives_and_ambiguous_facts_are_not_silently_selected():
    raw = document("""
      <ix:nonFraction name="core:CurrentAssets" contextRef="current"
        unitRef="GBP">100</ix:nonFraction>
      <ix:nonFraction name="core:CurrentAssets" contextRef="current"
        unitRef="GBP">200</ix:nonFraction>
      <ix:nonFraction name="core:CashBankOnHand" contextRef="old" unitRef="GBP">300</ix:nonFraction>
      <ix:nonFraction name="core:NetAssetsLiabilities" contextRef="current"
        unitRef="GBP" sign="-">40</ix:nonFraction>""")
    result = parse_document(raw, "00012345", "2023-12-31")
    assert "current_assets" not in result["facts"] and "cash" not in result["facts"]
    assert result["conflicting_metrics"] == ["current_assets"]
    assert result["facts"]["net_assets"]["value"] == "-4E+1"
    assert result["identity_verified_in_document"]
    with pytest.raises(ValueError, match="identity"):
        parse_document(raw, "00054321", "2023-12-31")


def test_creditor_maturity_dimensions_are_explicitly_mapped():
    raw = document(
        """
      <ix:nonFraction name="core:Creditors" contextRef="creditors"
        unitRef="GBP">500</ix:nonFraction>""",
        """<x:context id="creditors"><x:entity><x:segment>
      <d:explicitMember dimension="core:MaturitiesOrExpirationPeriodsDimension">
        core:WithinOneYear</d:explicitMember>
      </x:segment></x:entity><x:period><x:instant>2023-12-31</x:instant></x:period></x:context>""",
    )
    result = parse_document(raw, "00012345", "2023-12-31")
    assert result["facts"]["current_liabilities"]["value"] == "5E+2"
    assert "noncurrent_liabilities" not in result["facts"]


def test_missing_is_not_zero_and_external_entities_are_rejected():
    assert parse_document(document(""), "00012345", "2023-12-31")["facts"] == {}
    with pytest.raises(ValueError, match="entities"):
        parse_document(
            b'<!DOCTYPE x [<!ENTITY private SYSTEM "file:///etc/passwd">]><x/>',
            "00012345",
            "2023-12-31",
        )


def test_monthly_availability_bound_is_separate_from_report_period():
    assert pipeline.month_shift("2025-02", -12) == "2024-02"
    assert pipeline.month_end(pipeline.month_shift("2024-01", 1)) == "2024-02-29"
    assert pipeline.month_end(pipeline.month_shift("2024-02", 1)) > "2024-02-29"


def test_flow_facts_require_duration_contexts():
    raw = document("""<ix:nonFraction name="core:ProfitLoss" contextRef="current"
                       unitRef="GBP">500</ix:nonFraction>""")
    assert "profit_loss" not in parse_document(raw, "00012345", "2023-12-31")["facts"]


@pytest.mark.parametrize(
    "member,namespace,accepted",
    [
        ("Original", "http://xbrl.frc.org.uk/business", True),
        ("Revised", "http://xbrl.frc.org.uk/business", False),
        ("Original", "https://example.test/untrusted", False),
    ],
)
def test_original_dimension_is_metadata_only_in_trusted_taxonomy(member, namespace, accepted):
    context = f'''<x:context id="original"><x:entity><x:segment>
      <d:explicitMember xmlns:b="{namespace}" dimension="b:OriginalRevisedDataDimension">
      b:{member}</d:explicitMember></x:segment></x:entity>
      <x:period><x:instant>2023-12-31</x:instant></x:period></x:context>'''
    result = parse_document(
        document(
            """<ix:nonFraction name="core:CurrentAssets"
       contextRef="original" unitRef="GBP">123</ix:nonFraction>""",
            context,
        ),
        "00012345",
        "2023-12-31",
    )
    assert ("current_assets" in result["facts"]) is accepted


def test_original_dimension_does_not_hide_conflicts_or_entity_mismatch():
    context = """<x:context id="original"><x:entity><x:identifier>00012345</x:identifier>
      <x:segment><d:explicitMember dimension="core:OriginalRevisedDataDimension">
      core:Original</d:explicitMember></x:segment></x:entity>
      <x:period><x:instant>2023-12-31</x:instant></x:period></x:context>"""
    facts = """<ix:nonFraction name="core:CurrentAssets" contextRef="current"
      unitRef="GBP">100</ix:nonFraction>
      <ix:nonFraction name="core:CurrentAssets" contextRef="original"
      unitRef="GBP">200</ix:nonFraction>"""
    result = parse_document(document(facts, context), "00012345", "2023-12-31")
    assert result["conflicting_metrics"] == ["current_assets"]
    result = parse_document(
        document(facts, context.replace(">00012345<", ">00054321<")), "00012345", "2023-12-31"
    )
    assert result["facts"]["current_assets"]["value"] == "1E+2"


@pytest.mark.parametrize(
    "value,scale,quarantined",
    [
        ("-2", "0", True),
        ("00012345", "0", True),
        ("2", "3", True),
        ("2.5", "0", False),
        ("0", "0", False),
    ],
)
def test_employee_quality_quarantines_field_and_preserves_raw(value, scale, quarantined):
    context = """<x:context id="duration"><x:entity/>
      <x:period><x:startDate>2023-01-01</x:startDate><x:endDate>2023-12-31</x:endDate></x:period></x:context>
      <x:unit id="pure"><x:measure>x:pure</x:measure></x:unit>"""
    facts = f'''<ix:nonFraction name="core:AverageNumberEmployeesDuringPeriod"
      contextRef="duration" unitRef="pure" scale="{scale}">{value}</ix:nonFraction>
      <ix:nonFraction name="core:NetAssetsLiabilities" contextRef="current"
      unitRef="GBP">-50</ix:nonFraction>'''
    result = parse_document(document(facts, context), "00012345", "2023-12-31")
    assert ("average_employees" not in result["facts"]) is quarantined
    assert result["source_facts"]["average_employees"]["source_text"] == value
    assert result["facts"]["net_assets"]["value"] == "-5E+1"


def test_extreme_amount_is_quarantined_without_losing_other_metrics():
    raw = document("""<ix:nonFraction name="core:Equity" contextRef="current"
      unitRef="GBP">999000000000</ix:nonFraction>
      <ix:nonFraction name="core:CurrentAssets" contextRef="current"
      unitRef="GBP">0</ix:nonFraction>""")
    result = parse_document(raw, "00012345", "2023-12-31")
    assert "equity" not in result["facts"]
    assert result["facts"]["current_assets"]["value"] == "0"
    assert result["source_facts"]["equity"]["value"] == "9.99E+11"


def test_current_balance_identity_only_warns_and_keeps_source_values():
    from uk_financials.quality import validate_facts

    facts = {
        key: {"value": value, "unit": "GBP"}
        for key, value in {
            "current_assets": "100",
            "current_liabilities": "50",
            "net_current_assets": "99",
        }.items()
    }
    accepted, issues = validate_facts(facts, "00012345")
    assert accepted == facts
    assert issues[0]["action"] == "retain_with_warning"


def test_current_frc_inventory_and_cash_aliases_preserve_zero():
    raw = document("""
      <ix:nonFraction name="core:TotalInventories" contextRef="current"
        unitRef="GBP">0</ix:nonFraction>
      <ix:nonFraction name="core:CashCashEquivalents" contextRef="current"
        unitRef="GBP">100</ix:nonFraction>""")
    result = parse_document(raw, "00012345", "2023-12-31")
    assert result["facts"]["stocks"]["value"] == "0"
    assert result["facts"]["cash"]["value"] == "1E+2"


def test_range_index_and_member_crc_without_full_download(tmp_path, monkeypatch):
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr("Prod_00012345_20231231.html", b"original financial evidence")
    payload = stream.getvalue()
    ranges = []

    def respond(request):
        assert request.headers["range"].startswith("bytes=")
        interval = request.headers["range"][6:]
        if interval.startswith("-"):
            start, end = max(0, len(payload) + int(interval)), len(payload) - 1
        else:
            start, end = map(int, interval.split("-"))
            end = min(end, len(payload) - 1)
        ranges.append((start, end))
        return httpx.Response(
            206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{len(payload)}",
                "ETag": '"frozen"',
            },
            content=payload[start : end + 1],
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(archives, "CLIENT", client)
        manifest, entries = archives.index_archive("https://example.test/source.zip", tmp_path)
        assert archives.member_bytes(manifest, entries[0]) == b"original financial evidence"
        before = len(ranges)
        assert archives.index_archive("https://example.test/source.zip", tmp_path)[0] == manifest
        assert len(ranges) == before


def test_left_join_retains_missing_events_and_rejects_future_financials(tmp_path):
    events = [
        {"event_id": "first", "company_id": "00012345", "reference_month": "2025-02"},
        {"event_id": "second", "company_id": "", "reference_month": "2025-02"},
    ]
    source = tmp_path / "events.csv"
    source.write_text("source evidence")
    entry = {
        "company_id": "00012345",
        "period_end": "2023-12-31",
        "filing_month": "2024-01",
        "available_by": "2024-02-29",
        "url": "https://example.test/source.zip",
        "member": "source.html",
        "archive": {"etag": "frozen", "archiveSize": 100},
        "offset": 0,
        "crc32": 123,
    }
    report_id = pipeline.document_id(entry)
    result = {
        "report_id": report_id,
        "entry": entry,
        "status": "parsed",
        "raw_sha256": "a" * 64,
        "raw_cache": "source.gz",
        "identity_verified_in_document": True,
        "conflicting_metrics": [],
        "facts": {"cash": {"value": "0", "unit": "GBP"}},
    }
    pair = ("00012345", "2024-02")
    output = tmp_path / "output"
    output.mkdir()
    pipeline.deliver(
        events,
        source,
        output,
        {pair: [entry]},
        {report_id: result},
        {pair: result},
        {},
        {},
        12,
        36,
        "parser",
    )
    with (output / "event-financials.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2 and rows[0]["cash"] == "0" and rows[0]["cash_missing"] == "False"
    assert rows[0]["revenue"] == "" and rows[0]["revenue_missing"] == "True"
    assert rows[1]["financial_missing"] == "True" and rows[1]["cash"] == ""
    assert json.loads((output / "report.json").read_text())["joinedRows"] == 2
    entry["available_by"] = "2024-03-31"
    with pytest.raises(ValueError, match="observation-time"):
        pipeline.deliver(
            events,
            source,
            output,
            {pair: [entry]},
            {report_id: result},
            {pair: result},
            {},
            {},
            12,
            36,
            "parser",
        )
