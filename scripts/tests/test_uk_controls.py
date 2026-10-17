"""Stable time-window, risk-set and matching contracts for historical controls."""

import gzip
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_uk_controls import historical_name  # noqa: E402
from uk_financials.controls import (  # noqa: E402
    age_band,
    case_frame,
    control_eligible,
    latest_pool,
    registry_group,
    sample_pairs,
)


def test_future_case_can_be_an_earlier_control_but_horizon_event_cannot():
    history = {"00012345": ["2023-02"]}
    assert control_eligible("00012345", "2020-01", "2021-01", history)
    assert not control_eligible("00012345", "2022-02", "2023-02", history)
    assert not control_eligible("00012345", "2024-01", "2025-01", history)
    assert not control_eligible("00012345", "2025-01", "2026-01", {})
    assert not control_eligible("NI012345", "2020-01", "2021-01", {})


def test_matching_bands_and_registry_coverage():
    assert registry_group("00012345") == "EW_company"
    assert registry_group("SC012345") == "SC_company"
    assert registry_group("SO012345") == "SC_LLP"
    assert registry_group("OC012345") == "EW_LLP"
    assert registry_group("FC012345") == ""
    assert age_band("2024-01", "2023-07") == "01_06"
    assert age_band("2024-01", "2023-06") == "07_12"
    assert age_band("2024-01", "2022-12") == "13_24"
    assert age_band("2024-01", "2021-12") == "25_36"


def test_display_name_uses_the_selected_historical_reporting_context(tmp_path):
    source = tmp_path / "report.gz"
    raw = b"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:x="http://www.xbrl.org/2003/instance" xmlns:core="http://xbrl.frc.org.uk/core">
      <x:context id="past"><x:period><x:instant>2020-12-31</x:instant></x:period></x:context>
      <x:context id="later"><x:period><x:instant>2021-12-31</x:instant></x:period></x:context>
      <ix:nonNumeric name="core:EntityCurrentLegalOrRegisteredName" contextRef="past">
        Historical company</ix:nonNumeric>
      <ix:nonNumeric name="core:EntityCurrentLegalOrRegisteredName" contextRef="later">
        Later company</ix:nonNumeric></html>"""
    source.write_bytes(gzip.compress(raw))
    assert historical_name(source, "2020-12-31") == "Historical company"
    assert historical_name(source, "2019-12-31") == ""


def database(path):
    connection = sqlite3.connect(path)
    connection.execute("""CREATE TABLE filings (
        company TEXT, period_end TEXT, filing_month TEXT, member TEXT,
        offset INTEGER, compressed_size INTEGER, size INTEGER, crc INTEGER, compression INTEGER
    )""")
    return connection


def filing(company, end, month, member):
    return (company, end, month, member, 10, 10, 20, 123, 8)


def test_latest_selection_rejects_future_archive_and_future_accounting_period(tmp_path):
    with database(tmp_path / "test.sqlite") as connection:
        connection.executemany(
            "INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?)",
            [
                filing("00012345", "2022-12-31", "2023-02", "valid"),
                filing("00012345", "2023-12-31", "2023-03", "future_period"),
                filing("00054321", "2022-12-31", "2023-04", "future_archive"),
            ],
        )
        manifests = {"2023-02": {"url": "https://example.test/archive"}}
        pool = list(latest_pool(connection, "2023-04", manifests))
    assert len(pool) == 1
    assert pool[0]["member"] == "valid"
    assert pool[0]["available_by"] == "2023-03-31"


def test_monthly_matching_uses_controls_without_replacement(tmp_path):
    path = tmp_path / "test.sqlite"
    with database(path) as connection:
        connection.execute(
            "INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?)",
            filing("00012345", "2022-12-31", "2023-02", "valid"),
        )
    cases = [
        {"company_id": c, "observation_month": "2023-04", "entry": {"filing_month": "2023-02"}}
        for c in ("00054321", "00054322")
    ]
    manifests = {"2023-02": {"url": "https://example.test/archive"}}
    pairs, unmatched, _ = sample_pairs(path, cases, manifests, {})
    assert len(pairs) == len(unmatched) == 1
    assert pairs[0]["control_entry"]["company_id"] == "00012345"


def test_controls_are_not_reused_across_observation_months(tmp_path):
    path = tmp_path / "test.sqlite"
    with database(path) as connection:
        connection.execute(
            "INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?)",
            filing("00012345", "2022-12-31", "2023-02", "valid"),
        )
    cases = [
        {"company_id": company, "observation_month": month, "entry": {"filing_month": "2023-02"}}
        for company, month in (("00054321", "2023-04"), ("00054322", "2023-05"))
    ]
    manifests = {"2023-02": {"url": "https://example.test/archive"}}
    pairs, unmatched, _ = sample_pairs(path, cases, manifests, {})
    assert len(pairs) == len(unmatched) == 1


def test_cases_without_baseline_evidence_are_retained_as_excluded(tmp_path):
    import csv

    events = tmp_path / "events.csv"
    fields = [
        "company_id",
        "label_candidate",
        "is_first_observed_month",
        "reference_month",
        "company_name",
        "event_id",
        "review_reasons",
    ]
    with events.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            dict(
                zip(fields, ["00012345", "True", "True", "2021-04", "Name", "one", ""], strict=True)
            )
        )
    selection = tmp_path / "selection.gz"
    with gzip.open(selection, "wt") as stream:
        stream.write(
            json.dumps({"company_id": "00012345", "observation_month": "2020-04", "entries": []})
            + "\n"
        )
    eligible, excluded, total = case_frame(events, selection, {})
    assert total == len(excluded) == 1 and not eligible
    assert excluded[0]["exclusion_reason"] == "no_historical_electronic_filing_in_shared_window"
