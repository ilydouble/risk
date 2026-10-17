"""Verify every observation association and original cohort field without rewriting it."""

import gzip
import json
from collections import Counter
from itertools import zip_longest

from prepare_uk_basic_information import COHORT, OUTPUT, read_csv
from prepare_uk_financials import sha, write_json
from uk_financials.basic import FIELDS, age_days


def validate(output=OUTPUT):
    baseline = {row["report_id"]: row for row in read_csv(COHORT / "baseline-reports.csv")}
    profiles = {}
    with gzip.open(output / "historical-basic-profiles.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            key = row["report_id"]
            assert key not in profiles
            if key in baseline:
                for field in (
                    "company_id",
                    "period_end",
                    "availability_upper_bound",
                    "member",
                    "member_sha256",
                    "member_crc32",
                    "member_size",
                    "archive_url",
                ):
                    assert row[field] == baseline[key][field], (key, field)
            for field, fact in row["facts"].items():
                assert field not in row["conflicts"]
                assert fact["period_end"] == row["period_end"]
                assert fact["value"] == row["values"][field]
                if field.startswith("registered_office_"):
                    assert any(
                        d["member"].endswith(":RegisteredOffice") for d in fact["dimensions"]
                    )
            assert set(row["values"]) == set(row["facts"])
            profiles[key] = {
                field: row[field]
                for field in ("company_id", "period_end", "availability_upper_bound", "values")
            }
    counts = Counter()
    cohort_samples = set()
    for original, row, combined in zip_longest(
        read_csv(COHORT / "features.csv"),
        read_csv(output / "features.csv"),
        read_csv(output / "sample-basic-information.csv"),
    ):
        assert original and row and combined
        assert row["sample_id"] not in cohort_samples
        cohort_samples.add(row["sample_id"])
        assert all(row[field] == value for field, value in original.items())
        assert all(not field.startswith(("snapshot_", "event_reference_")) for field in row)
        assert (
            row["sample_id"] == combined["sample_id"]
            and row["company_id"] == combined["company_id"]
        )
        profile = profiles.get(row["baseline_report_id"])
        assert (
            row["historical_registry_status"] == ""
            and row["historical_registry_status_missing"] == "True"
        )
        if profile:
            assert profile["company_id"] == row["company_id"]
            assert profile["availability_upper_bound"] <= row["observation_date"]
            assert profile["period_end"] <= row["observation_date"]
        values = profile["values"] if profile else {}
        for field in FIELDS:
            expected = str(values.get(field, ""))
            assert row["historical_" + field] == expected
            assert row["historical_" + field] == combined["historical_" + field]
            assert row["historical_" + field + "_missing"] == str(expected == "")
        assert row["historical_company_age_days"] == str(
            age_days(row["observation_date"], values.get("incorporation_date", ""))
        )
        counts["sampleRows"] += 1
    for original, row in zip_longest(
        read_csv(COHORT / "excluded-cases.csv"),
        read_csv(output / "excluded-case-basic-information.csv"),
    ):
        assert original and row
        assert all(row[field] == value for field, value in original.items())
        counts["excludedCaseRows"] += 1
    for filename in ("labels.csv", "matches.csv", "excluded-cases.csv"):
        assert sha(output / filename) == sha(COHORT / filename)
    contract = json.loads((output / "feature-contract.json").read_text())
    allowed = contract["numericFeatureAllowlist"] + contract["categoricalFeatureAllowlist"]
    assert all(not name.startswith(("snapshot_", "event_reference_")) for name in allowed)
    assert "historical_registry_status" not in allowed
    companies = set()
    for row in read_csv(output / "company-reference.csv"):
        assert row["company_id"] not in companies
        companies.add(row["company_id"])
        for width in range(2, 6):
            code = row[f"event_reference_sic07_{width}_digit"]
            assert code == "" or (code.isdigit() and len(code) == width)
        assert row["event_reference_baseline_availability_verified"] == "False"
        counts["snapshotMatchedCompanies"] += row["snapshot_missing"] == "False"
        counts["snapshotOrEventReferenceMatchedCompanies"] += (
            row["snapshot_missing"] == "False" or row["event_reference_missing"] == "False"
        )
    assert counts["sampleRows"] == 209192 and counts["excludedCaseRows"] == 22078
    assert len(companies) == 229907 and len(profiles) == 208853
    assert {row["company_id"] for row in read_csv(output / "features.csv")} | {
        row["company_id"] for row in read_csv(output / "excluded-case-basic-information.csv")
    } == companies
    result = {
        "passed": True,
        **counts,
        "uniqueCompanies": len(companies),
        "verifiedHistoricalReports": len(profiles),
        "originalFinancialValuesLabelsAndPairsPreserved": True,
        "snapshotAndEventReferenceExcludedFromModelFeatures": True,
    }
    write_json(output / "validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    validate()
