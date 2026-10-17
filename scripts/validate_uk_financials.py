"""Independently audit a delivered financial join and its retained source evidence."""

import argparse
import calendar
import csv
import gzip
import hashlib
import json
import zlib
from collections import Counter
from datetime import date
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def shifted_end(month, offset):
    year, number = map(int, month.split("-"))
    year, index = divmod(year * 12 + number - 1 + offset, 12)
    return date(year, index + 1, calendar.monthrange(year, index + 1)[1]).isoformat()


def audit(events_path, output):
    report = json.loads((output / "report.json").read_text())
    assert digest(events_path) == report["eventsSha256"]
    reports = {}
    raw_bytes = 0
    cache_root = None
    identity_verified = Counter()
    for row in rows(output / "financial-reports.csv"):
        key = row["report_id"]
        assert key not in reports
        expected_id = hashlib.sha256((row["archive_url"] + "#" + row["member"]).encode())
        assert expected_id.hexdigest() == key
        source_path = Path(row["raw_cache_path"])
        if not source_path.exists() and not source_path.is_absolute():
            source_path = output.resolve().parents[1] / "backend" / source_path
        cache_root = source_path.parent.parent.parent
        raw = gzip.decompress(source_path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row["member_sha256"]
        assert zlib.crc32(raw) == int(row["member_crc32"])
        raw_bytes += len(raw)
        identity_verified[row["document_identity_verified"]] += 1
        reports[key] = row
    facts = {}
    fact_count = 0
    with gzip.open(output / "financial-facts.jsonl.gz", "rt") as stream:
        for fact in map(json.loads, stream):
            key = fact["report_id"]
            source = reports[key]
            assert fact["member_sha256"] == source["member_sha256"]
            assert fact["period_end"] == source["period_end"]
            assert fact["metric"] not in facts.setdefault(key, {})
            value = fact["source_text"].strip().replace("\u00a0", "").replace(" ", "")
            form = fact["format"].rsplit(":", 1)[-1].lower()
            parentheses = value.startswith("(") and value.endswith(")")
            if parentheses:
                value = value[1:-1]
            if value in ("-", "—", "–"):
                assert form in ("zerodash", "numdash")
                value = "0"
            if form in ("numcommadecimal", "num-comma-decimal", "numdotcomma"):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
            amount = Decimal(value) * Decimal(10) ** int(fact["scale"])
            if parentheses or fact["sign"] == "-":
                amount = -abs(amount)
            assert amount.is_finite() and amount == Decimal(fact["value"])
            facts[key][fact["metric"]] = (fact["value"], fact["unit"])
            fact_count += 1
    assert set(facts) == set(reports)
    count, matched, zeros = 0, 0, 0
    coverage, reasons, years = Counter(), Counter(), {}
    seen = set()
    companies, matched_companies = set(), set()
    for event, row in zip_longest(rows(events_path), rows(output / "event-financials.csv")):
        assert event is not None and row is not None
        assert all(row[field] == value for field, value in event.items())
        assert row["event_id"] not in seen
        seen.add(row["event_id"])
        if row["company_id"]:
            companies.add(row["company_id"])
        horizon = int(row["prediction_horizon_months"])
        assert horizon == report["horizonMonths"]
        observation = shifted_end(event["reference_month"], -horizon)
        assert row["observation_date"] == observation
        assert row["exact_filing_date"] == ""
        key = row["financial_report_id"]
        assert (row["financial_missing"] == "True") == (not key)
        year = event["reference_month"][:4]
        years.setdefault(year, Counter())["events"] += 1
        if key:
            matched += 1
            matched_companies.add(row["company_id"])
            years[year]["matched"] += 1
            source = reports[key]
            assert row["company_id"] == source["company_id"]
            assert row["report_period_end"] == source["period_end"] <= observation
            assert row["filing_month"] == source["filing_month"]
            assert row["availability_upper_bound"] == source["availability_upper_bound"]
            assert source["availability_upper_bound"] <= observation
            assert source["availability_upper_bound"] == shifted_end(source["filing_month"], 1)
            assert not row["financial_missing_reason"]
            assert int(row["financial_fact_count"]) == len(facts[key])
            assert int(row["report_age_days"]) == (
                date.fromisoformat(observation) - date.fromisoformat(source["period_end"])
            ).days
        else:
            assert row["financial_missing_reason"]
        reasons[row["financial_missing_reason"] or "matched"] += 1
        for metric in report["metricObservedRows"]:
            expected = facts.get(key, {}).get(metric)
            assert row[metric] == (expected[0] if expected else "")
            assert row[metric + "_missing"] == str(expected is None)
            if expected:
                assert row["financial_currency"] == expected[1] or metric == "average_employees"
                zeros += Decimal(expected[0]) == 0
                coverage[metric] += 1
        count += 1
    assert count == report["eventRows"] == report["joinedRows"]
    assert matched == report["matchedEventRows"]
    assert dict(reasons) == report["missingReasons"]
    assert {metric: coverage[metric] for metric in report["metricObservedRows"]} == report[
        "metricObservedRows"
    ]
    assert len(reports) == report["uniqueFinancialReports"]
    ties, pairs, empty = [], 0, 0
    with gzip.open(output / "selection.jsonl.gz", "rt") as stream:
        for pair in map(json.loads, stream):
            pairs += 1
            entries = pair["entries"]
            empty += not entries
            observation = shifted_end(pair["observation_month"], 0)
            for entry in entries:
                assert entry["company_id"] == pair["company_id"]
                assert entry["period_end"] <= observation
                assert entry["available_by"] <= observation
            if len(entries) > 1 and (
                entries[0]["period_end"], entries[0]["filing_month"]
            ) == (entries[1]["period_end"], entries[1]["filing_month"]):
                ties.append({
                    "company_id": pair["company_id"],
                    "observation_month": pair["observation_month"],
                    "members": [e["member"] for e in entries],
                })
    (output / "selection-ties-review.json").write_text(json.dumps(ties, indent=2))
    manifests = json.loads((output / "archive-manifests.json").read_text())
    assert len(manifests) == report["indexesScanned"] == 107
    assert not report["indexErrors"]
    assert cache_root is not None
    directory_bytes = 0
    for month, manifest in manifests.items():
        directory = gzip.decompress((cache_root / "indexes" / month / "directory.gz").read_bytes())
        assert hashlib.sha256(directory).hexdigest() == manifest["directorySha256"]
        assert len(directory) == manifest["directorySize"]
        directory_bytes += len(directory)
    result = {
        "passed": True,
        "eventRowsPreserved": count,
        "matchedEventRows": matched,
        "uniqueValidCompanyNumbers": len(companies),
        "uniqueMatchedCompanies": len(matched_companies),
        "matchedPercentage": round(matched / count * 100, 2),
        "validatedRawReports": len(reports),
        "validatedRawBytes": raw_bytes,
        "validatedArchiveIndexes": len(manifests),
        "validatedArchiveDirectoryBytes": directory_bytes,
        "validatedFacts": fact_count,
        "observedZeroValues": zeros,
        "documentIdentityVerification": dict(identity_verified),
        "companyObservationPairs": pairs,
        "pairsWithoutArchiveCandidates": empty,
        "sameMonthAndPeriodCandidateTies": len(ties),
        "byEventYear": years,
        "monthlyAvailabilityIsAssumedNotExactFilingDate": True,
        "normalControlsIncluded": False,
        "consolidatedVersusStandaloneScopeFullyVerified": False,
    }
    (output / "validation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    audit(args.events, args.output)
