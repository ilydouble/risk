"""Stable event-data boundaries: identities, dates, procedure roles and deduplication."""

import csv
import importlib.util
import io
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "adverse_events", Path(__file__).resolve().parents[2] / "scripts/prepare_uk_adverse_events.py"
)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def row(identity="12345", case_type="In Administration", month="2020-02"):
    return {
        "company_number": identity,
        "company_name": "EXAMPLE LIMITED",
        "register_location": "England/Wales",
        "case_type": case_type,
        "month_registered": month,
        "is_bulk": "",
        **{f"sic07_{i}_digit": "NA" for i in range(1, 6)},
    }


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12345", "00012345"),
        ("sc001234", "SC001234"),
        ("OC123456", "OC123456"),
        ("NA", ""),
        ("O1234567", ""),
        ("OC12345", ""),
    ],
)
def test_ids_preserve_zeros_and_do_not_guess_typos(value, expected):
    assert pipeline.company_identity(value)[0] == expected


def test_month_precision_is_not_fabricated_exact_date():
    record = pipeline.normalize(row(case_type="Compulsory Liquidation"), "a" * 64, "source", 2)
    assert record["event_date"] == record["published_at"] == ""
    assert record["reference_interval_end"] == "2020-02-29"
    assert record["reference_date_basis"] == "court_order_month"
    assert record["source_release_date"] != record["reference_interval_start"]


def test_utf8_and_legacy_names_are_decoded_without_replacement():
    name = "RAWSHÁ LOUNGE LTD"
    assert pipeline.decode_name(name.encode().decode("latin1")) == (name, "utf-8")
    assert pipeline.decode_name("CAFÊ") == ("CAFÊ", "cp1252")


def test_candidates_exclude_followup_invalid_ids_and_duplicates(tmp_path):
    rows = [
        row(month="2019-12"),
        row(),
        row(),
        row(identity="45678", case_type="Administration to CVL"),
        row(identity="56789", case_type="Moratorium"),
        row(identity="NA"),
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    archive = tmp_path / "source.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("Record-level.csv", stream.getvalue())
        zipped.writestr("Metadata.csv", "Release date,20/01/2026")
        zipped.writestr("README.txt", "Coverage to 31 December 2025")
    output = tmp_path / "output"
    report = pipeline.prepare(archive, output)
    assert report["eventRecords"] == 5
    assert report["adverseEntryCandidates"] == 1
    assert report["exactDuplicateEvidenceRows"] == 1
    assert report["firstObservedCompanies"] == 0
    with (output / "events.csv").open(encoding="utf-8-sig", newline="") as f:
        events = list(csv.DictReader(f))
    assert events[0]["first_observed_adverse_month"] == "2019-12"
    assert events[0]["is_first_observed_month"] == "False"
    assert len({r["event_id"] for r in events}) == 5
    assert events[1]["duplicate_of_event_id"] == events[0]["event_id"]
