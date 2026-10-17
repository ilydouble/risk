"""Prepare auditable monthly adverse-event records from an official statistical release."""

import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from zipfile import ZipFile

RELEASE_PAGE = "https://www.gov.uk/government/statistics/company-insolvencies-december-2025"
SOURCE_URL = (
    "https://assets.publishing.service.gov.uk/media/696e184762bfa46d3881a24d/"
    "Record-level_data_for_England_Wales_and_Scotland_-_"
    "Company_Insolvency_Statistics_December_2025.zip"
)
RELEASE_DATE = "2026-01-20"
CASE_TYPES = {
    "Compulsory Liquidation": ("compulsory_liquidation", "primary_adverse_entry"),
    "Creditors Voluntary Liquidation": ("creditors_voluntary_liquidation", "primary_adverse_entry"),
    "In Administration": ("administration", "primary_adverse_entry"),
    "Corporate Voluntary Arrangement": ("company_voluntary_arrangement", "primary_adverse_entry"),
    "Administrative Receiver": ("administrative_receivership", "primary_adverse_entry"),
    "Administration to CVL": ("administration_to_cvl", "subsequent_procedure"),
    "Moratorium": ("moratorium", "protective_procedure"),
}
FIELDS = [
    "event_id",
    "company_id",
    "company_number_raw",
    "company_id_status",
    "company_name",
    "name_encoding",
    "register_location",
    "event_type",
    "case_type_raw",
    "event_role",
    "reference_month",
    "reference_date_basis",
    "date_precision",
    "reference_interval_start",
    "reference_interval_end",
    "event_date",
    "published_at",
    "source_release_date",
    "is_bulk_raw",
    "is_bulk_status",
    "duplicate_of_event_id",
    "label_candidate",
    "first_observed_adverse_month",
    "is_first_observed_month",
    "review_reasons",
    "sic07_1_digit",
    "sic07_2_digit",
    "sic07_3_digit",
    "sic07_4_digit",
    "sic07_5_digit",
    "source_member",
    "source_record_number",
    "source_row_sha256",
    "source_archive_sha256",
    "source_url",
    "source_release_page",
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def company_identity(value):
    raw = value.strip()
    upper = raw.upper()
    if re.fullmatch(r"[0-9]{1,8}", raw):
        return raw.zfill(8), "numeric_leading_zeros_restored"
    if re.fullmatch(r"[A-Z]{2}[0-9]{6}", upper):
        return upper, "prefix_format_checked"
    return "", "needs_registry_review"


def decode_name(value):
    raw = value.encode("latin1")
    for encoding in ("utf-8", "cp1252", "latin1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise AssertionError("Latin-1 must preserve every byte")


def normalize(row, archive_sha, member, record_number):
    identity, identity_status = company_identity(row["company_number"])
    event_type, role = CASE_TYPES[row["case_type"]]
    month = row["month_registered"]
    if not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", month):
        raise ValueError(f"Invalid source reference month at record {record_number}")
    year, number = map(int, month.split("-"))
    name, encoding = decode_name(row["company_name"])
    reasons = []
    if not identity:
        reasons.append("company_number_requires_registry_review")
    if encoding != "utf-8":
        reasons.append("company_name_legacy_encoding")
    basis = "companies_house_registration_month"
    if event_type == "compulsory_liquidation":
        if row["register_location"] == "England/Wales":
            basis = "court_order_month"
        else:
            basis = "source_compulsory_liquidation_month"
            reasons.append("scottish_compulsory_date_basis_requires_verification")
    bulk = row["is_bulk"].strip()
    if bulk not in ("", "N", "Y"):
        raise ValueError("Unknown bulk insolvency flag")
    return {
        "event_id": stable_hash([archive_sha, member, record_number]),
        "company_id": identity,
        "company_number_raw": row["company_number"],
        "company_id_status": identity_status,
        "company_name": name,
        "name_encoding": encoding,
        "register_location": row["register_location"],
        "event_type": event_type,
        "case_type_raw": row["case_type"],
        "event_role": role,
        "reference_month": month,
        "reference_date_basis": basis,
        "date_precision": "month",
        "reference_interval_start": date(year, number, 1).isoformat(),
        "reference_interval_end": date(
            year, number, calendar.monthrange(year, number)[1]
        ).isoformat(),
        "event_date": "",
        "published_at": "",
        "source_release_date": RELEASE_DATE,
        "is_bulk_raw": bulk,
        "is_bulk_status": "flagged_bulk" if bulk == "Y" else "not_flagged_in_source",
        "duplicate_of_event_id": "",
        "review_reasons": ";".join(reasons),
        **{key: row[key] for key in row if key.startswith("sic07_")},
        "source_member": member,
        "source_record_number": record_number,
        "source_row_sha256": stable_hash(row),
        "source_archive_sha256": archive_sha,
        "source_url": SOURCE_URL,
        "source_release_page": RELEASE_PAGE,
    }


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(archive, output, start="2020-01", end="2025-12"):
    if output.exists():
        raise ValueError("Output already exists; choose a new version")
    if start > end:
        raise ValueError("Start month is after end month")
    if any(not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", value) for value in (start, end)):
        raise ValueError("Expected YYYY-MM bounds")
    archive_sha = digest(archive)
    with ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("Official source archive failed CRC validation")
        members = [
            n for n in zipped.namelist() if n.startswith("Record-level") and n.endswith(".csv")
        ]
        if len(members) != 1:
            raise ValueError("Expected one official record-level CSV")
        member = members[0]
        with (
            zipped.open(member) as binary,
            io.TextIOWrapper(binary, encoding="latin1", newline="") as stream,
        ):
            source = list(csv.DictReader(stream))
        # This transformer is bound to the frozen release, not any similarly named CSV.
        metadata = zipped.read("Metadata.csv")
        readme = zipped.read("README.txt")
        if b"20/01/2026" not in metadata or b"31 December 2025" not in readme:
            raise ValueError("Unexpected source release; review its metadata before converting")
    all_rows = [normalize(row, archive_sha, member, i) for i, row in enumerate(source, start=2)]
    canonical = {}
    first_month = {}
    for row in all_rows:
        if row["source_row_sha256"] in canonical:
            row["duplicate_of_event_id"] = canonical[row["source_row_sha256"]]
        else:
            canonical[row["source_row_sha256"]] = row["event_id"]
        eligible = bool(
            row["company_id"]
            and row["event_role"] == "primary_adverse_entry"
            and row["is_bulk_raw"] != "Y"
            and not row["duplicate_of_event_id"]
        )
        row["label_candidate"] = eligible
        if eligible:
            identity = row["company_id"]
            first_month[identity] = min(
                first_month.get(identity, "9999-99"), row["reference_month"]
            )
    for row in all_rows:
        month = first_month.get(row["company_id"], "")
        row["first_observed_adverse_month"] = month
        row["is_first_observed_month"] = bool(
            row["label_candidate"] and row["reference_month"] == month
        )
    rows = [r for r in all_rows if start <= r["reference_month"] <= end]
    if not rows:
        raise ValueError("No events in selected reference-month range")
    output.mkdir(parents=True)
    originals = output / "source"
    originals.mkdir()
    shutil.copyfile(archive, originals / "official-record-level.zip")
    (originals / "Metadata.csv").write_bytes(metadata)
    (originals / "README.txt").write_bytes(readme)
    write_csv(output / "events.csv", rows, FIELDS)
    candidates = [r for r in rows if r["label_candidate"]]
    write_csv(output / "adverse-entry-candidates.csv", candidates, FIELDS)
    reviews = [r for r in rows if r["review_reasons"] or r["duplicate_of_event_id"]]
    write_csv(output / "review.csv", reviews, FIELDS)
    first_groups = defaultdict(list)
    for row in candidates:
        if row["is_first_observed_month"]:
            first_groups[row["company_id"]].append(row)
    history_start = min(r["reference_month"] for r in all_rows)
    first_rows = [
        {
            "company_id": identity,
            "company_name": group[0]["company_name"],
            "first_observed_adverse_month": group[0]["reference_month"],
            "event_types": ";".join(sorted({r["event_type"] for r in group})),
            "evidence_event_ids": ";".join(r["event_id"] for r in group),
            "observation_history_start": history_start,
            "first_ever_event_proven": False,
        }
        for identity, group in sorted(first_groups.items())
    ]
    write_csv(
        output / "first-observed-adverse-month.csv",
        first_rows,
        [
            "company_id",
            "company_name",
            "first_observed_adverse_month",
            "event_types",
            "evidence_event_ids",
            "observation_history_start",
            "first_ever_event_proven",
        ],
    )
    years = sorted({r["reference_month"][:4] for r in rows})
    types = sorted(CASE_TYPES)
    counts = Counter((r["reference_month"][:4], r["case_type_raw"]) for r in rows)
    write_csv(
        output / "year-type-counts.csv",
        [
            {"year": year, "case_type": kind, "source_records": counts[year, kind]}
            for year in years
            for kind in types
        ],
        ["year", "case_type", "source_records"],
    )
    report = {
        "schemaVersion": 1,
        "sourceReleaseDate": RELEASE_DATE,
        "sourceUrl": SOURCE_URL,
        "sourceReleasePage": RELEASE_PAGE,
        "sourceArchiveSha256": archive_sha,
        "pipelineSha256": digest(Path(__file__)),
        "selectionBasis": "official_reference_month_not_notice_publication_date",
        "referenceMonthStart": start,
        "referenceMonthEnd": end,
        "sourceRows": len(all_rows),
        "sourceHistoryStart": min(r["reference_month"] for r in all_rows),
        "eventRecords": len(rows),
        "validFormatCompanyIds": len({r["company_id"] for r in rows} - {""}),
        "rowsRequiringCompanyIdReview": sum(not r["company_id"] for r in rows),
        "exactDuplicateEvidenceRows": sum(bool(r["duplicate_of_event_id"]) for r in rows),
        "adverseEntryCandidates": len(candidates),
        "firstObservedCompanies": len(first_rows),
        "reviewRows": len(reviews),
        "caseTypeCounts": dict(Counter(r["case_type_raw"] for r in rows)),
        "yearCounts": dict(Counter(r["reference_month"][:4] for r in rows)),
        "dateBasisCounts": dict(Counter(r["reference_date_basis"] for r in rows)),
        "nameEncodingCounts": dict(Counter(r["name_encoding"] for r in rows)),
        "coverage": ["England", "Wales", "Scotland"],
        "northernIrelandIncluded": False,
        "exactEventDatesAvailable": False,
        "individualPublicationDatesAvailable": False,
        "dataUse": "Statistical research; not verified current status of individual companies",
        "limitations": [
            "Reference months mix registration month and compulsory court-order month.",
            "Interval bounds delimit the supplied month; they are not imputed event dates.",
            "Release date is not the date an individual event first became public.",
            "First observed since 2015 is not first ever; history before 2015 is not covered.",
            "Missing source event does not establish a negative label or follow-up completeness.",
            "A future release may revise these historical records.",
            "Industry/name attributes here are event-record attributes, not pre-event features.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2020-01")
    parser.add_argument("--end", default="2025-12")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.source_zip, args.output, args.start, args.end),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
