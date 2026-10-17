"""Attach event-record basic information as reference evidence, never as baseline features."""

import csv
from collections import Counter, defaultdict
from pathlib import Path

from prepare_uk_basic_information import COHORT, OUTPUT, ROOT, read_csv
from prepare_uk_financials import sha, write_csv, write_json

EVENTS = ROOT / "outputs/uk-adverse-events-2020-2025-v1/events.csv"
FIELDS = (
    "company_id",
    "event_id",
    "company_name",
    "register_location",
    "reference_month",
    "source_release_date",
    "event_type",
    "event_role",
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
)


def event_reference(events):
    """Do not pick a later record just to increase field completeness."""
    selected = min(events, key=lambda r: (r["reference_month"], r["event_id"])) if events else {}
    result = {"event_reference_count": len(events), "event_reference_missing": not bool(events)}
    for field in FIELDS:
        if field == "company_id":
            continue
        value = selected.get(field, "")
        if field in ("sic07_2_digit", "sic07_3_digit", "sic07_4_digit", "sic07_5_digit") and value:
            width = int(field.split("_")[1])
            value = value.zfill(width) if value.isdigit() and len(value) <= width else ""
        elif field == "sic07_1_digit" and value == "NA":
            value = ""
        result["event_reference_" + field] = value
    result["event_reference_baseline_availability_verified"] = False
    return result


def run(output=OUTPUT):
    companies = {r["company_id"] for r in read_csv(output / "company-reference.csv")}
    grouped = defaultdict(list)
    with (output / "event-basic-evidence.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in read_csv(EVENTS):
            if row["company_id"] in companies:
                grouped[row["company_id"]].append(row)
                writer.writerow({field: row[field] for field in FIELDS})
    references = {company: event_reference(grouped.get(company, [])) for company in companies}
    write_csv(
        output / "company-event-reference.csv",
        ({"company_id": company, **references[company]} for company in sorted(companies)),
        ["company_id"] + list(event_reference([])),
    )
    coverage = {}
    for filename in (
        "company-reference.csv",
        "sample-basic-information.csv",
        "excluded-case-basic-information.csv",
    ):
        counts = Counter()
        path = output / filename
        temporary = path.with_suffix(".tmp")
        with (
            path.open(encoding="utf-8-sig", newline="") as source,
            temporary.open("w", encoding="utf-8-sig", newline="") as destination,
        ):
            reader = csv.DictReader(source)
            writer = csv.DictWriter(
                destination,
                fieldnames=[f for f in reader.fieldnames if not f.startswith("event_reference_")]
                + list(event_reference([])),
            )
            writer.writeheader()
            for row in reader:
                ref = references[row["company_id"]]
                writer.writerow({**row, **ref})
                counts["rows"] += 1
                counts["event_reference_matched"] += not ref["event_reference_missing"]
                counts["event_reference_sic2007"] += bool(ref["event_reference_sic07_5_digit"])
                counts["snapshot_or_event_reference_matched"] += (
                    row["snapshot_missing"] == "False" or not ref["event_reference_missing"]
                )
        temporary.replace(path)
        coverage[filename] = dict(counts)
    write_json(output / "event-reference-coverage.json", coverage)
    write_json(
        output / "event-reference-manifest.json",
        {
            "source": str(EVENTS),
            "sourceSha256": sha(EVENTS),
            "sourceReleaseDate": "2026-01-20",
            "pipelineSha256": sha(Path(__file__)),
            "eventReferenceFieldsMustNotBeModelFeatures": True,
            "cohortLabelSha256": sha(COHORT / "labels.csv"),
            "warning": (
                "Event-record SIC is not verified at the observation date; "
                "controls may have events after their prediction horizon."
            ),
        },
    )
    print(coverage)


if __name__ == "__main__":
    run()
