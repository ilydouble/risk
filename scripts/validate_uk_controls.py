"""Audit delivered matched controls, source evidence and the feature/label boundary."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import zlib
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from prepare_uk_financials import month_end, month_shift, sha, write_csv, write_json
from uk_financials.controls import age_band, rank, read_rows, registry_group


def source_events(path):
    first = {}
    with ZipFile(path) as zipped:
        member = next(
            n for n in zipped.namelist() if n.startswith("Record-level") and n.endswith(".csv")
        )
        with io.TextIOWrapper(zipped.open(member), encoding="latin1", newline="") as stream:
            for row in csv.DictReader(stream):
                company = row["company_number"].strip().upper()
                if company.isdigit() and len(company) <= 8:
                    company = company.zfill(8)
                elif not re.fullmatch(r"[A-Z]{2}[0-9]{6}", company):
                    continue
                first[company] = min(first.get(company, "9999-99"), row["month_registered"])
    return first


def check_fact(fact):
    source = fact["source_text"].strip().replace("\u00a0", "").replace(" ", "")
    parentheses = source.startswith("(") and source.endswith(")")
    if parentheses:
        source = source[1:-1]
    form = fact["format"].rsplit(":", 1)[-1].lower()
    if source in ("-", "—", "–"):
        assert form in ("zerodash", "numdash")
        source = "0"
    if form in ("numcommadecimal", "num-comma-decimal", "numdotcomma"):
        source = source.replace(".", "").replace(",", ".")
    else:
        source = source.replace(",", "")
    amount = Decimal(source) * Decimal(10) ** int(fact["scale"])
    if parentheses or fact["sign"] == "-":
        amount = -abs(amount)
    assert amount.is_finite() and amount == Decimal(fact["value"])


def audit(output, events, archive):
    report = json.loads((output / "report.json").read_text())
    assert report["sampling"]["eventsSha256"] == sha(events)
    assert report["sampling"]["eventArchiveSha256"] == sha(archive)
    first = source_events(archive)
    originals = {}
    for row in read_rows(events):
        originals[row["event_id"]] = (
            row["company_id"],
            row["reference_month"],
            row["label_candidate"],
            row["is_first_observed_month"],
        )
    reports, raw_bytes = {}, 0
    for row in read_rows(output / "baseline-reports.csv"):
        key = row["report_id"]
        assert key not in reports
        assert (
            key == hashlib.sha256((row["archive_url"] + "#" + row["member"]).encode()).hexdigest()
        )
        assert row["status"] in ("parsed", "no_supported_monetary_facts"), row
        assert row["document_identity_verified"] == "True", row["member"]
        raw = gzip.decompress(Path(row["raw_cache_path"]).read_bytes())
        assert len(raw) == int(row["member_size"])
        assert zlib.crc32(raw) == int(row["member_crc32"])
        assert hashlib.sha256(raw).hexdigest() == row["member_sha256"]
        raw_bytes += len(raw)
        reports[key] = row
    facts, fact_count = {}, 0
    with gzip.open(output / "baseline-facts.jsonl.gz", "rt") as stream:
        for fact in map(json.loads, stream):
            key = fact["report_id"]
            assert fact["period_end"] == reports[key]["period_end"]
            assert fact["metric"] not in facts.setdefault(key, {})
            check_fact(fact)
            facts[key][fact["metric"]] = (fact["value"], fact["unit"])
            fact_count += 1
    features = {}
    for row in read_rows(output / "features.csv"):
        key = row["sample_id"]
        assert key not in features
        source = reports[row["baseline_report_id"]]
        observation = row["observation_date"]
        assert row["company_id"] == source["company_id"]
        assert source["period_end"] <= observation
        assert source["availability_upper_bound"] <= observation
        assert source["availability_upper_bound"] == month_end(
            month_shift(source["filing_month"], 1)
        )
        assert row["company_name"] == (source["historical_name"] or row["company_id"])
        assert row["company_name_missing"] == source["historical_name_missing"]
        assert row["financial_missing"] == str(source["status"] != "parsed")
        expected_facts = facts.get(source["report_id"], {})
        for field in row:
            if field.endswith("_missing") and field not in (
                "company_name_missing",
                "financial_missing",
            ):
                metric = field.removesuffix("_missing")
                value = expected_facts.get(metric)
                assert row[field] == str(value is None)
                assert row[metric] == (value[0] if value else "")
                if value and metric != "average_employees":
                    assert row["financial_currency"] == value[1]
        assert (
            int(row["report_age_days"])
            == (date.fromisoformat(observation) - date.fromisoformat(source["period_end"])).days
        )
        assert "label" not in row and "event_type" not in row and "target_event_month" not in row
        features[key] = row
    labels, companies, controls, cases = {}, set(), set(), set()
    later_events, coverage, by_year = 0, Counter(), {}
    pairs_seen = Counter()
    for row in read_rows(output / "labels.csv"):
        key = row["sample_id"]
        assert key not in labels
        feature = features[key]
        company, observation = row["company_id"], row["observation_month"]
        followup = row["followup_end_month"]
        assert (company, observation) not in companies
        companies.add((company, observation))
        assert feature["company_id"] == row["company_group_id"] == company
        assert feature["observation_date"] == month_end(observation)
        assert followup == month_shift(observation, 12) <= "2025-12"
        assert row["followup_start_month"] == month_shift(observation, 1)
        assert row["historical_register_status_verified"] == "False"
        role = row["role"]
        pairs_seen[row["pair_id"]] += 1
        if role == "control":
            assert row["label"] == "0" and row["target_event_month"] == ""
            assert not row["event_evidence_ids"]
            assert company not in controls
            assert first.get(company, "9999-99") > followup
            later_events += company in first
            controls.add(company)
            if registry_group(company).endswith("company"):
                assert int.from_bytes(rank(company), "big") % 16 == 0
        else:
            assert role == "case" and row["label"] == "1"
            assert row["target_event_month"] == followup
            assert company not in cases
            assert first[company] > observation
            cases.add(company)
            for event_id in row["event_evidence_ids"].split(";"):
                assert originals[event_id] == (company, followup, "True", "True")
        coverage[role + ":financial"] += feature["financial_missing"] == "False"
        coverage[role + ":name"] += feature["company_name_missing"] == "False"
        for field, value in feature.items():
            if field.endswith("_missing") and field not in (
                "company_name_missing",
                "financial_missing",
            ):
                coverage[role + ":" + field.removesuffix("_missing")] += value == "False"
        by_year.setdefault(followup[:4], Counter())[role] += 1
        labels[key] = row
    assert set(features) == set(labels)
    assert all(count == 2 for count in pairs_seen.values())
    matches = list(read_rows(output / "matches.csv"))
    assert len(matches) == len(pairs_seen) == len(cases) == len(controls) == report["pairedCases"]
    for match in matches:
        case, control = labels[match["case_sample_id"]], labels[match["control_sample_id"]]
        assert case["role"] == "case" and control["role"] == "control"
        assert case["pair_id"] == control["pair_id"] == match["pair_id"]
        assert (
            case["observation_month"] == control["observation_month"] == match["observation_month"]
        )
        assert case["followup_end_month"] == control["followup_end_month"]
        for label in (case, control):
            company = label["company_id"]
            assert registry_group(company) == match["registry_group"]
            source = reports[features[label["sample_id"]]["baseline_report_id"]]
            assert (
                age_band(label["observation_month"], source["filing_month"])
                == match["filing_age_band"]
            )
    excluded = list(read_rows(output / "excluded-cases.csv"))
    assert len(excluded) == report["excludedCases"]
    assert not cases.intersection(row["company_id"] for row in excluded)
    assert len(cases) + len(excluded) == report["sourceFirstObservedCaseCompanies"]
    assert len(features) == report["combinedRows"]
    contract = json.loads((output / "feature-contract.json").read_text())
    allowed = contract["numericFeatureAllowlist"] + contract["categoricalFeatureAllowlist"]
    assert not set(allowed).intersection(
        {
            "sample_id",
            "company_id",
            "company_name",
            "observation_date",
            "baseline_report_id",
            "label",
            "pair_id",
        }
    )
    assert set(allowed).issubset(next(iter(features.values())))
    output_counts = []
    for key, value in sorted(coverage.items()):
        role, metric = key.split(":", 1)
        output_counts.append(
            {
                "role": role,
                "metric": metric,
                "observed_rows": value,
                "rows": len(cases),
                "observed_percent": round(value / len(cases) * 100, 2),
            }
        )
    write_csv(
        output / "coverage.csv",
        output_counts,
        ["role", "metric", "observed_rows", "rows", "observed_percent"],
    )
    result = {
        "passed": True,
        "pairedCases": len(cases),
        "controlRows": len(controls),
        "combinedRows": len(features),
        "excludedCaseRowsPreserved": len(excluded),
        "caseAndControlCompaniesAcrossDifferentMonths": len(cases & controls),
        "controlsWithRecordedEventAfterTheirHorizon": later_events,
        "verifiedBaselineReports": len(reports),
        "verifiedRawBytes": raw_bytes,
        "verifiedFacts": fact_count,
        "byFollowupYear": by_year,
        "historicalRegisterStatusVerified": False,
        "endpoint": "recorded_formal_insolvency_not_all_adverse_states",
        "monthlyAvailabilityIsAssumed": True,
        "allFinancialMissingRowsPreserved": True,
    }
    write_json(output / "validation.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--event-archive", type=Path, required=True)
    args = parser.parse_args()
    audit(args.output, args.events, args.event_archive)
