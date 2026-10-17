"""Independently verify repaired fields against facts, source metadata and immutable v2."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from repair_uk_research_data import PRESERVED, json_lines
from uk_financials.facts import ALIASES


def validate(base, output):
    for name in PRESERVED:
        assert sha(base / name) == sha(output / name), name
    hyperedge_manifest = json.loads((output / "hyperedge-manifest.json").read_text())
    if hyperedge_manifest.get("qualityRevision"):
        for name, digest in hyperedge_manifest["preservedFiles"].items():
            assert sha(output / name) == digest, name
    original_reports = {
        row["report_id"]: tuple(
            row[field]
            for field in [
                "company_id",
                "period_end",
                "availability_upper_bound",
                "member_sha256",
                "member_size",
                "member_crc32",
            ]
        )
        for row in json_lines(base / "historical-basic-profiles.jsonl.gz")
    }
    profiles = {}
    countries = set()
    for row in json_lines(output / "historical-basic-profiles.jsonl.gz"):
        rid = row["report_id"]
        assert rid not in profiles
        assert original_reports[rid] == tuple(
            row[field]
            for field in [
                "company_id",
                "period_end",
                "availability_upper_bound",
                "member_sha256",
                "member_size",
                "member_crc32",
            ]
        )
        code = row["values"].get("country_of_incorporation", "")
        assert code in {"", "GB", "AX", "AF", "IE", "US", "FR", "DE", "NL"}
        profiles[rid] = {
            "company": row["company_id"],
            "period": row["period_end"],
            "available": row["availability_upper_bound"],
            "country": code,
        }
        if code:
            countries.add(row["company_id"])
    assert profiles.keys() == original_reports.keys()
    values, units = defaultdict(dict), defaultdict(set)
    counts = Counter()
    for fact in json_lines(output / "financial-facts.jsonl.gz"):
        rid, metric = fact["report_id"], fact["metric"]
        assert rid in profiles and metric not in values[rid]
        assert fact["period_end"] == profiles[rid]["period"]
        number = Decimal(fact["value"])
        assert number.is_finite()
        if metric == "average_employees":
            assert 0 <= number <= 100000 and int(fact["scale"]) == 0
            assert not (
                profiles[rid]["company"].isdigit() and number == int(profiles[rid]["company"])
            )
        else:
            if fact["unit"] in {"GBP", "EUR", "USD"}:
                assert abs(number) < Decimal("1e11")
            units[rid].add(fact["unit"])
        assert all(d["member"] != "Revised" and not d["typed"] for d in fact["dimensions"])
        values[rid][metric] = fact["value"]
        counts["acceptedFacts"] += 1
    assert all(len(unit) <= 1 for unit in units.values())
    quarantine = set()
    for issue in json_lines(output / "financial-quality-issues.jsonl.gz"):
        assert issue["report_id"] in profiles
        if issue["action"] == "quarantine":
            key = issue["report_id"], issue["metric"]
            quarantine.add(key)
            assert issue["metric"] not in values[issue["report_id"]]
    source_seen = set()
    for fact in json_lines(output / "financial-source-facts.jsonl.gz"):
        key = fact["report_id"], fact["metric"]
        assert key not in source_seen
        source_seen.add(key)
        if key not in quarantine:
            assert values[key[0]][key[1]] == fact["value"]
        else:
            assert key[1] not in values[key[0]]
    assert len(source_seen) == counts["acceptedFacts"] + len(quarantine)
    seen = set()
    allowed_changed = (
        set(ALIASES)
        | {key + "_missing" for key in ALIASES}
        | {
            "financial_missing",
            "financial_missing_reason",
            "financial_currency",
            "historical_country_of_incorporation",
            "historical_country_of_incorporation_missing",
        }
    )
    original_money, repaired_money = 0, 0
    for old, row in zip_longest(read_csv(base / "features.csv"), read_csv(output / "features.csv")):
        assert old and row and row["sample_id"] not in seen
        seen.add(row["sample_id"])
        assert all(row[key] == value for key, value in old.items() if key not in allowed_changed)
        rid = row["baseline_report_id"]
        assert profiles[rid]["company"] == row["company_id"]
        assert profiles[rid]["period"] <= row["observation_date"]
        assert profiles[rid]["available"] <= row["observation_date"]
        for metric in ALIASES:
            assert row[metric] == values[rid].get(metric, "")
            assert row[metric + "_missing"] == str(row[metric] == "")
            if (rid, metric) in quarantine:
                assert row[metric] == ""
        has_money = any(value for key, value in values[rid].items() if key != "average_employees")
        assert row["financial_missing"] == str(not has_money)
        assert row["financial_currency"] == next(iter(units[rid]), "")
        assert row["historical_country_of_incorporation"] == profiles[rid]["country"]
        assert row["historical_country_of_incorporation_missing"] == str(
            not profiles[rid]["country"]
        )
        original_money += old["financial_missing"] == "False"
        repaired_money += has_money
    for old, row in zip_longest(
        read_csv(base / "excluded-case-basic-information.csv"),
        read_csv(output / "excluded-case-basic-information.csv"),
    ):
        assert old and row
        assert all(
            row[key] == value
            for key, value in old.items()
            if not key.startswith("historical_country_of_incorporation")
        )
        rid = row["historical_basic_report_id"]
        assert row["historical_country_of_incorporation"] == (
            profiles[rid]["country"] if rid else ""
        )
        counts["excludedEventRowsPreserved"] += 1
    for old, row in zip_longest(
        read_csv(base / "company-reference.csv"), read_csv(output / "company-reference.csv")
    ):
        assert old and row and all(row[key] == value for key, value in old.items())
        counts["companyReferencesPreserved"] += 1
    for row in read_csv(output / "basic-information-gaps.csv"):
        assert row["no_historical_country_of_incorporation_observed"] == str(
            row["node_id"] not in countries
        )
    assert len(profiles) == 208853 and len(seen) == 209192
    assert counts["excludedEventRowsPreserved"] == 22078
    assert counts["companyReferencesPreserved"] == 229907
    assumption = json.loads((output / "quality-report.json").read_text())["researchAssumption"]
    assert (
        assumption["currentRegisterEqualsHistoricalObservation"]
        and not assumption["historicallyVerified"]
    )
    result = {
        "passed": True,
        "reports": len(profiles),
        "observationSamples": len(seen),
        **counts,
        "originalMonetaryNonmissing": original_money,
        "repairedMonetaryNonmissing": repaired_money,
        "quarantinedReportMetrics": len(quarantine),
        "graphLabelsEventsPairsAndAllCompaniesPreserved": True,
        "assumptionIsUserAcceptedNotHistoricalVerification": True,
    }
    write_json(output / "validation.json", result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(args.base, args.output)
