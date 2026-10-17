"""Extract local disclosed comparatives and make point-in-time financial trend features."""

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import zlib
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import ExitStack
from itertools import islice
from pathlib import Path

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from repair_uk_research_data import json_lines
from uk_financials.facts import ALIASES, parse_document
from uk_financials.trends import FLOWS, choose_history, trend_features

ROOT = Path(__file__).resolve().parents[1]
EXTRA_REPORTS = (
    ROOT
    / "datasets/archive/uk-research-20261017/uk-financials-2020-2025-h12-v1/financial-reports.csv"
)
SOURCE_FIELDS = [
    "report_id",
    "company_id",
    "period_end",
    "filing_month",
    "availability_upper_bound",
    "archive_url",
    "archive_etag",
    "member",
    "member_sha256",
    "member_crc32",
    "member_size",
    "raw_cache_path",
    "source_metadata_file",
    "is_v3_baseline_report",
]


def source_reports(base, extra):
    reports = {}
    for row in json_lines(base / "historical-basic-profiles.jsonl.gz"):
        rid = row["report_id"]
        if rid in reports:
            raise ValueError("Duplicate baseline report metadata")
        row.update(
            source_metadata_file="v3/historical-basic-profiles.jsonl.gz", is_v3_baseline_report=True
        )
        reports[rid] = {key: row.get(key, "") for key in SOURCE_FIELDS}
    research = {row["company_id"] for row in read_csv(base / "company-reference.csv")}
    unavailable = []
    if extra and extra.exists():
        for row in read_csv(extra):
            rid = row["report_id"]
            if rid in reports or row["company_id"] not in research:
                continue
            cache = Path(row["raw_cache_path"])
            if not cache.is_absolute():
                cache = (ROOT / "backend" / cache).resolve()
            if not cache.exists():
                unavailable.append(
                    {"report_id": rid, "reason": "additional_local_cache_unavailable"}
                )
                continue
            row.update(
                raw_cache_path=str(cache),
                source_metadata_file=str(extra.resolve()),
                is_v3_baseline_report=False,
            )
            reports[rid] = {key: row.get(key, "") for key in SOURCE_FIELDS}
    return reports, unavailable


def parse_batch(reports):
    result = []
    for report in reports:
        raw = gzip.decompress(Path(report["raw_cache_path"]).read_bytes())
        if hashlib.sha256(raw).hexdigest() != report["member_sha256"] or zlib.crc32(raw) != int(
            report["member_crc32"]
        ):
            raise ValueError("Frozen local filing integrity mismatch: " + report["report_id"])
        if report["member_size"] and int(report["member_size"]) != len(raw):
            raise ValueError("Frozen local filing size mismatch")
        report = {
            **report,
            "member_size_verified": bool(report["member_size"]),
            "member_size": len(raw),
        }
        periods = parse_document(
            raw, report["company_id"], report["period_end"], include_comparatives=True
        )
        result.append((report, periods))
    return result


def row_identity(report_id, end):
    return hashlib.sha256((report_id + "|" + end).encode()).hexdigest()


def history_columns(report, end, parsed):
    facts = parsed["facts"]
    currencies = {fact["unit"] for key, fact in facts.items() if key != "average_employees"}
    row = {
        "history_id": row_identity(report["report_id"], end),
        "company_id": report["company_id"],
        "report_id": report["report_id"],
        "report_period_end": report["period_end"],
        "period_end": end,
        "available_by_assumed": report["availability_upper_bound"],
        "period_kind": "current" if end == report["period_end"] else "comparative",
        "financial_currency": next(iter(currencies), ""),
        "financial_missing": not bool(currencies),
        "accepted_metric_count": len(facts),
        "quality_issue_count": len(parsed["quality_issues"]),
        "conflicting_metrics": "|".join(parsed["conflicting_metrics"]),
    }
    for metric in ALIASES:
        fact = facts.get(metric)
        row[metric] = fact["value"] if fact else ""
        row[metric + "_missing"] = fact is None
        if metric in FLOWS:
            row[metric + "_period_start"] = fact.get("period_start") or "" if fact else ""
    return row


def compact_history(row, facts):
    return {
        "history_id": row["history_id"],
        "company_id": row["company_id"],
        "report_id": row["report_id"],
        "report_end": row["report_period_end"],
        "end": row["period_end"],
        "available": row["available_by_assumed"],
        "currency": row["financial_currency"],
        "facts": {
            key: (fact["value"], fact["unit"], fact.get("period_start"))
            for key, fact in facts.items()
        },
    }


def run(base, output, extra, workers):
    if output.exists() or output.resolve().is_relative_to(base.resolve()):
        raise ValueError("Choose a fresh extension directory outside the base")
    manifest = json.loads((base / "delivery-manifest.json").read_text())
    if (
        not manifest["validated"]
        or not json.loads((base / "validation.json").read_text())["passed"]
    ):
        raise ValueError("Validated v3 base required")
    for name in [
        "features.csv",
        "labels.csv",
        "historical-basic-profiles.jsonl.gz",
        "company-reference.csv",
        "feature-contract.json",
    ]:
        if sha(base / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Base input checksum mismatch: " + name)
    reports, unavailable = source_reports(base, extra)
    output.mkdir(parents=True)
    write_json(output / "unavailable-additional-reports.json", unavailable)
    iterator = iter(reports.values())
    company_history = defaultdict(list)
    baseline_rows = {}
    counts, issues = Counter(), Counter()
    period_counts = Counter()
    metadata_fields = SOURCE_FIELDS + [
        "member_size_verified",
        "filing_date_exact",
        "filing_date_exact_verified",
    ]
    sample_metadata = next(iter(reports.values()))
    dummy = history_columns(
        sample_metadata,
        sample_metadata["period_end"],
        {"facts": {}, "quality_issues": [], "conflicting_metrics": []},
    )
    with ExitStack() as stack:
        history_stream = stack.enter_context(
            (output / "financial-history.csv").open("w", encoding="utf-8-sig", newline="")
        )
        history_writer = csv.DictWriter(history_stream, fieldnames=list(dummy))
        history_writer.writeheader()
        source_stream = stack.enter_context(
            (output / "financial-report-sources.csv").open("w", encoding="utf-8-sig", newline="")
        )
        source_writer = csv.DictWriter(source_stream, fieldnames=metadata_fields)
        source_writer.writeheader()
        gzips = {
            name: stack.enter_context(gzip.open(output / name, "wt", encoding="utf-8"))
            for name in [
                "history-facts.jsonl.gz",
                "history-source-facts.jsonl.gz",
                "history-quality-issues.jsonl.gz",
            ]
        }
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = set()

            def submit():
                batch = list(islice(iterator, 64))
                if batch:
                    pending.add(pool.submit(parse_batch, batch))

            for _ in range(workers * 2):
                submit()
            while pending:
                completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    for report, periods in future.result():
                        source_writer.writerow(
                            {**report, "filing_date_exact": "", "filing_date_exact_verified": False}
                        )
                        period_counts[len(periods)] += 1
                        for end, parsed in periods.items():
                            row = history_columns(report, end, parsed)
                            history_writer.writerow(row)
                            compact = compact_history(row, parsed["facts"])
                            company_history[report["company_id"]].append(compact)
                            if report["is_v3_baseline_report"] and end == report["period_end"]:
                                baseline_rows[report["report_id"]] = compact
                            counts["history_rows"] += 1
                            counts["accepted_facts"] += len(parsed["facts"])
                            counts["comparative_rows"] += end < report["period_end"]
                            for key, name in [
                                ("facts", "history-facts.jsonl.gz"),
                                ("source_facts", "history-source-facts.jsonl.gz"),
                            ]:
                                for fact in parsed[key].values():
                                    gzips[name].write(
                                        json.dumps(
                                            {
                                                "history_id": row["history_id"],
                                                "report_id": report["report_id"],
                                                "company_id": report["company_id"],
                                                **fact,
                                            }
                                        )
                                        + "\n"
                                    )
                            for issue in parsed["quality_issues"]:
                                issues[issue["action"] + ":" + issue["reason"]] += 1
                                gzips["history-quality-issues.jsonl.gz"].write(
                                    json.dumps(
                                        {
                                            "history_id": row["history_id"],
                                            "report_id": report["report_id"],
                                            "period_end": end,
                                            **issue,
                                        }
                                    )
                                    + "\n"
                                )
                        counts["reports"] += 1
                    submit()
                if counts["reports"] // 4096 != counts["last_progress_bucket"]:
                    counts["last_progress_bucket"] = counts["reports"] // 4096
                    write_json(
                        output / "progress.json",
                        {"stage": "parse", "expected_reports": len(reports), **counts},
                    )
                    print(f"HISTORY {counts['reports']}/{len(reports)} reports", flush=True)

    roles = {row["sample_id"]: row["role"] for row in read_csv(base / "labels.csv")}
    coverage, by_role, statuses = Counter(), defaultdict(Counter), Counter()
    metrics = Counter()
    periods_by_sample = Counter()
    with ExitStack() as stack:
        feature_stream = stack.enter_context(
            (output / "features.csv").open("w", encoding="utf-8-sig", newline="")
        )
        link_stream = stack.enter_context(
            (output / "sample-history-links.csv").open("w", encoding="utf-8-sig", newline="")
        )
        link_writer = csv.DictWriter(
            link_stream,
            fieldnames=[
                "sample_id",
                "company_id",
                "observation_date",
                "baseline_report_id",
                "history_id",
                "report_id",
                "period_end",
                "available_by_assumed",
                "period_rank",
            ],
        )
        link_writer.writeheader()
        feature_writer = None
        for row in read_csv(base / "features.csv"):
            baseline = baseline_rows[row["baseline_report_id"]]
            if (
                baseline["company_id"] != row["company_id"]
                or baseline["available"] > row["observation_date"]
            ):
                raise ValueError("Baseline identity or availability mismatch")
            for metric in ALIASES:
                if row[metric] != (
                    baseline["facts"][metric][0] if metric in baseline["facts"] else ""
                ):
                    raise ValueError(
                        "v3 baseline financial value drift: " + row["sample_id"] + ":" + metric
                    )
            history = choose_history(baseline, company_history[row["company_id"]])
            trend = trend_features(history)
            if set(trend) & row.keys():
                raise ValueError("Trend features must not overwrite base columns")
            if feature_writer is None:
                feature_writer = csv.DictWriter(feature_stream, fieldnames=list(row) + list(trend))
                feature_writer.writeheader()
            feature_writer.writerow({**row, **trend})
            for rank, period in enumerate(history):
                link_writer.writerow(
                    {
                        "sample_id": row["sample_id"],
                        "company_id": row["company_id"],
                        "observation_date": row["observation_date"],
                        "baseline_report_id": row["baseline_report_id"],
                        "history_id": period["history_id"],
                        "report_id": period["report_id"],
                        "period_end": period["end"],
                        "available_by_assumed": period["available"],
                        "period_rank": rank,
                    }
                )
            role = roles[row["sample_id"]]
            coverage["samples"] += 1
            coverage["samples_with_previous_period"] += len(history) >= 2
            coverage["samples_with_three_periods"] += len(history) >= 3
            has_delta = has_slope = False
            for metric in ALIASES:
                for suffix in [
                    "previous",
                    "delta",
                    "relative_change",
                    "three_period_slope_per_year",
                ]:
                    nonmissing = trend[f"{metric}_{suffix}"] != ""
                    metrics[metric + ":" + suffix] += nonmissing
                    by_role[role][metric + ":" + suffix] += nonmissing
                has_delta |= trend[metric + "_delta"] != ""
                has_slope |= trend[metric + "_three_period_slope_per_year"] != ""
                statuses[metric + ":" + trend[metric + "_trend_status"]] += 1
            coverage["samples_with_any_comparable_delta"] += has_delta
            coverage["samples_with_any_three_period_slope"] += has_slope
            by_role[role]["samples"] += 1
            by_role[role]["samples_with_any_comparable_delta"] += has_delta
            by_role[role]["samples_with_any_three_period_slope"] += has_slope
            periods_by_sample[len(history)] += 1
            if coverage["samples"] % 20000 == 0:
                print(f"TRENDS {coverage['samples']}/209192 samples", flush=True)
    shutil.copyfile(base / "labels.csv", output / "labels.csv")
    write_json(
        output / "history-report.json",
        {
            "format": "uk-local-financial-history-v1",
            "baseDirectory": str(base.resolve()),
            "baseDeliverySha256": sha(base / "delivery-manifest.json"),
            "inputFiles": {
                name: sha(base / name)
                for name in ["features.csv", "labels.csv", "historical-basic-profiles.jsonl.gz"]
            },
            "additionalReportMetadata": {"file": str(extra.resolve()), "sha256": sha(extra)}
            if extra and extra.exists()
            else None,
            "sourceReports": counts,
            "additional_reports": sum(not row["is_v3_baseline_report"] for row in reports.values()),
            "sourceCompanies": len(company_history),
            "disclosedPeriodsPerReport": period_counts,
            "selectedPeriodsPerSample": periods_by_sample,
            "coverage": coverage,
            "metricCoverage": metrics,
            "byRole": by_role,
            "trendStatuses": statuses,
            "qualityIssues": issues,
            "exactFilingDatesVerified": False,
            "baselineAndComparativesVersionPolicy": (
                "baseline current fixed; baseline comparatives preferred; "
                "other report available no later than baseline availability bound; "
                "fixed whole-report version per period"
            ),
            "comparativeAvailability": (
                "same conservative filing-month-plus-one-month-end bound as source report, "
                "not comparative period end"
            ),
            "externalApiOrRelationshipCollectionPerformed": False,
        },
    )
    write_csv(
        output / "trend-coverage.csv",
        [
            {
                "metric": metric,
                **{
                    suffix: metrics[metric + ":" + suffix]
                    for suffix in [
                        "previous",
                        "delta",
                        "relative_change",
                        "three_period_slope_per_year",
                    ]
                },
            }
            for metric in ALIASES
        ],
        ["metric", "previous", "delta", "relative_change", "three_period_slope_per_year"],
    )
    write_json(output / "progress.json", {"stage": "parsed_and_joined", **coverage})
    print(json.dumps({"source_reports": counts, "coverage": coverage}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extra-reports", type=Path, default=EXTRA_REPORTS)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(args.base, args.output, args.extra_reports, args.workers)
