"""Reparse frozen filings into a new graph delivery without resampling or graph mutation."""

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import zlib
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from itertools import islice
from pathlib import Path

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from uk_financials.basic import parse_basic_document
from uk_financials.countries import normalize_country
from uk_financials.facts import ALIASES, parse_document
from uk_financials.quality import POLICY_VERSION

PRESERVED = [
    "nodes.csv",
    "edges.csv",
    "groups.csv",
    "group-memberships.csv",
    "membership-evidence.csv",
    "labels.csv",
    "matches.csv",
    "events.csv",
    "event-node-links.csv",
    "out-of-scope-events.csv",
    "node-observations.csv",
    "excluded-cases.csv",
    "enterprise-graph.graphml",
    "enterprise-and-hyperedges.graphml",
]


def json_lines(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            yield json.loads(line)


def repair_batch(profiles):
    results = []
    for old in profiles:
        raw = gzip.decompress(Path(old["raw_cache_path"]).read_bytes())
        if (
            hashlib.sha256(raw).hexdigest() != old["member_sha256"]
            or len(raw) != int(old["member_size"])
            or zlib.crc32(raw) != int(old["member_crc32"])
        ):
            raise ValueError(f"Raw filing integrity mismatch: {old['report_id']}")
        financial = parse_document(raw, old["company_id"], old["period_end"])
        basic = parse_basic_document(raw, old["company_id"], old["period_end"])
        profile = {
            **old,
            **basic,
            "conflicting_metrics": ";".join(financial["conflicting_metrics"]),
            "financial_quality_issue_count": len(financial["quality_issues"]),
        }
        results.append({"profile": profile, "financial": financial})
    return results


def country_columns(profile, prefix="historical_"):
    fact = profile.get("facts", {}).get("country_of_incorporation", {})
    evidence = [
        row
        for row in profile.get("country_normalizations", [])
        if row["field"] == "country_of_incorporation"
    ]
    raw_values = sorted({row["raw_value"] for row in evidence})
    statuses = sorted({row["status"] for row in evidence})
    jurisdictions = {row["jurisdiction"] for row in evidence if row["code"] == fact.get("value")}
    code = fact.get("value", "")
    return {
        prefix + "country_of_incorporation": code,
        prefix + "country_of_incorporation_missing": not bool(code),
        prefix + "country_of_incorporation_raw": " | ".join(raw_values),
        prefix + "country_of_incorporation_jurisdiction": next(iter(jurisdictions))
        if len(jurisdictions) == 1
        else "",
        prefix + "country_of_incorporation_normalization_status": "conflicting_country_codes"
        if "country_of_incorporation" in profile.get("conflicts", [])
        else "|".join(statuses) or "missing",
    }


def transform_csv(source, destination, transform):
    iterator = iter(read_csv(source))
    first = next(iterator)
    transformed = transform(first)
    temporary = destination.with_suffix(".csv.part")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(transformed))
        writer.writeheader()
        writer.writerow(transformed)
        for row in iterator:
            writer.writerow(transform(row))
    temporary.replace(destination)


def run(base, output, workers):
    if (
        output.exists()
        or base.resolve() == output.resolve()
        or base.resolve() in output.resolve().parents
    ):
        raise ValueError("Choose a new version outside the immutable base dataset")
    manifest = json.loads((base / "delivery-manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if sha(base / name) != expected["sha256"]:
            raise ValueError(f"Base dataset digest mismatch: {name}")
    shutil.copytree(base, output)
    provenance = output / "provenance/v2"
    provenance.mkdir(parents=True)
    for name in [
        "README.md",
        "delivery-manifest.json",
        "validation.json",
        "coverage.json",
        "basic-information-gaps.csv",
        "basic-information-gaps.json",
    ]:
        (output / name).replace(provenance / name)
    (output / "README.md").write_text("# v3 正在生成\n校验通过前请勿使用。\n", encoding="utf-8")

    compact, counters = {}, Counter()
    source_iter = iter(json_lines(base / "historical-basic-profiles.jsonl.gz"))
    stream_names = [
        "historical-basic-profiles.jsonl.gz",
        "financial-facts.jsonl.gz",
        "financial-source-facts.jsonl.gz",
        "financial-quality-issues.jsonl.gz",
    ]
    streams = {name: gzip.open(output / name, "wt", encoding="utf-8") for name in stream_names}
    issue_counts = Counter()
    report_metadata = []
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = set()

            def submit():
                batch = list(islice(source_iter, 64))
                if batch:
                    pending.add(pool.submit(repair_batch, batch))

            for _ in range(workers * 2):
                submit()
            while pending:
                completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    for result in future.result():
                        profile, financial = result["profile"], result["financial"]
                        rid = profile["report_id"]
                        if rid in compact:
                            raise ValueError("Duplicate report ID")
                        facts = financial["facts"]
                        units = {
                            fact["unit"]
                            for key, fact in facts.items()
                            if key != "average_employees"
                        }
                        country = country_columns(profile)
                        compact[rid] = {
                            "company_id": profile["company_id"],
                            "period_end": profile["period_end"],
                            "available_by": profile["availability_upper_bound"],
                            "values": {key: fact["value"] for key, fact in facts.items()},
                            "currency": next(iter(units), ""),
                            "country": country,
                            "quarantined": sorted(
                                {
                                    row["metric"]
                                    for row in financial["quality_issues"]
                                    if row["action"] == "quarantine"
                                }
                            ),
                            "warnings": sorted(
                                {
                                    row["reason"]
                                    for row in financial["quality_issues"]
                                    if row["action"] == "retain_with_warning"
                                }
                            ),
                        }
                        streams[stream_names[0]].write(json.dumps(profile) + "\n")
                        for key, filename in [
                            ("facts", stream_names[1]),
                            ("source_facts", stream_names[2]),
                        ]:
                            for fact in financial[key].values():
                                streams[filename].write(
                                    json.dumps({"report_id": rid, **fact}) + "\n"
                                )
                        for issue in financial["quality_issues"]:
                            issue_counts[issue["action"] + ":" + issue["reason"]] += 1
                            streams[stream_names[3]].write(
                                json.dumps(
                                    {"report_id": rid, "company_id": profile["company_id"], **issue}
                                )
                                + "\n"
                            )
                        counters["reports"] += 1
                        counters["accepted_facts"] += len(facts)
                        counters["source_facts"] += len(financial["source_facts"])
                        counters["original_dimension_accepted_facts"] += sum(
                            any(
                                d["axis"] == "OriginalRevisedDataDimension"
                                for d in fact["dimensions"]
                            )
                            for fact in facts.values()
                        )
                        counters["conflicting_metrics"] += len(financial["conflicting_metrics"])
                        report_metadata.append(
                            {
                                "report_id": rid,
                                "company_id": profile["company_id"],
                                "period_end": profile["period_end"],
                                "member_sha256": profile["member_sha256"],
                                "accepted_metrics": "|".join(sorted(facts)),
                                "conflicting_metrics": "|".join(financial["conflicting_metrics"]),
                                "quarantined_metrics": "|".join(compact[rid]["quarantined"]),
                            }
                        )
                    submit()
                if counters["reports"] // 2048 != counters["last_progress_bucket"]:
                    counters["last_progress_bucket"] = counters["reports"] // 2048
                    write_json(output / "repair-progress.json", counters)
                    print(f"REPARSED {counters['reports']} reports", flush=True)
    finally:
        for stream in streams.values():
            stream.close()
    write_csv(output / "financial-report-quality.csv", report_metadata, list(report_metadata[0]))
    feature_counts, changes, role_counts = Counter(), Counter(), defaultdict(Counter)
    labels = {row["sample_id"]: row for row in read_csv(base / "labels.csv")}
    metric_changes = Counter()
    financial_change_path = output / "financial-value-changes.csv"
    with financial_change_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "sample_id",
                "company_id",
                "report_id",
                "metric",
                "old_value",
                "new_value",
                "reason",
            ],
        )
        writer.writeheader()

        def repair_feature(row):
            report = compact[row["baseline_report_id"]]
            if (
                report["company_id"] != row["company_id"]
                or report["period_end"] > row["observation_date"]
                or report["available_by"] > row["observation_date"]
            ):
                raise ValueError("Report identity/time boundary changed")
            role = labels[row["sample_id"]]["role"]
            role_counts[role]["samples"] += 1
            had_money = row["financial_missing"] == "False"
            for key in ALIASES:
                previous, value = row[key], report["values"].get(key, "")
                if previous != value:
                    reason = (
                        "quality_quarantine"
                        if key in report["quarantined"]
                        else "reparsed_context_or_conflict"
                    )
                    writer.writerow(
                        {
                            "sample_id": row["sample_id"],
                            "company_id": row["company_id"],
                            "report_id": row["baseline_report_id"],
                            "metric": key,
                            "old_value": previous,
                            "new_value": value,
                            "reason": reason,
                        }
                    )
                    metric_changes[
                        key
                        + ":"
                        + (
                            "filled"
                            if previous == "" and value != ""
                            else "cleared"
                            if value == ""
                            else "changed"
                        )
                    ] += 1
                row[key], row[key + "_missing"] = value, value == ""
                role_counts[role]["nonmissing:" + key] += value != ""
            has_money = any(
                value for key, value in report["values"].items() if key != "average_employees"
            )
            changes["monetary_missing_recovered"] += not had_money and has_money
            changes["monetary_now_missing"] += had_money and not has_money
            role_counts[role]["monetary_nonmissing"] += has_money
            row["financial_missing"] = not has_money
            row["financial_missing_reason"] = (
                "" if has_money else "no_accepted_monetary_facts_after_quality_checks"
            )
            row["financial_currency"] = report["currency"]
            row["financial_quarantined_metrics"] = "|".join(report["quarantined"])
            row["financial_quality_warnings"] = "|".join(report["warnings"])
            row["financial_quality_policy"] = POLICY_VERSION
            old_country = row["historical_country_of_incorporation"]
            row.update(report["country"])
            changes["country_value_changed"] += (
                old_country != row["historical_country_of_incorporation"]
            )
            role_counts[role]["normalized_country_nonmissing"] += bool(
                row["historical_country_of_incorporation"]
            )
            feature_counts["rows"] += 1
            return row

        transform_csv(base / "features.csv", output / "features.csv", repair_feature)

    def repair_excluded(row):
        rid = row.get("historical_basic_report_id", "")
        row.update(compact[rid]["country"] if rid else country_columns({}))
        return row

    transform_csv(
        base / "excluded-case-basic-information.csv",
        output / "excluded-case-basic-information.csv",
        repair_excluded,
    )

    def repair_reference(row):
        for field, suffix in [
            ("snapshot_CountryOfOrigin", "country_of_origin"),
            ("snapshot_RegAddress.Country", "registered_office_country"),
        ]:
            country = normalize_country(row[field])
            row["reference_" + suffix + "_iso"] = country["code"]
            row["reference_" + suffix + "_jurisdiction"] = country["jurisdiction"]
            row["reference_" + suffix + "_normalization_status"] = country["status"]
        return row

    transform_csv(
        base / "company-reference.csv", output / "company-reference.csv", repair_reference
    )
    # Country gaps are observation/report-derived, so the old snapshot gap flags
    # remain reference-only; recompute just the field affected by normalization.
    country_observed = {
        report["company_id"]
        for report in compact.values()
        if report["country"]["historical_country_of_incorporation"]
    }
    gap_counts = Counter()

    def repair_gap(row):
        row["no_historical_country_of_incorporation_observed"] = (
            row["node_id"] not in country_observed
        )
        gap_counts.update(key for key, value in row.items() if value is True or value == "True")
        return row

    transform_csv(
        provenance / "basic-information-gaps.csv", output / "basic-information-gaps.csv", repair_gap
    )
    gap_summary = json.loads((provenance / "basic-information-gaps.json").read_text())
    gap_summary["missingCounts"] = gap_counts
    write_json(output / "basic-information-gaps.json", gap_summary)
    assumption = {
        "currentRegisterEqualsHistoricalObservation": True,
        "basis": "explicit_user_rough_research_assumption",
        "historicallyVerified": False,
        "appliesTo": "use_of_current_registry_attributes",
        "changesGraphOrLabels": False,
    }
    report = {
        "format": "uk-research-data-quality-v3",
        "base": str(base.resolve()),
        "qualityPolicy": POLICY_VERSION,
        "rawSourceChecks": "sha256_size_crc32_for_every_reparsed_report",
        "reports": counters,
        "qualityIssues": issue_counts,
        "changes": changes,
        "metricChanges": metric_changes,
        "byRole": role_counts,
        "researchAssumption": assumption,
    }
    write_json(output / "quality-report.json", report)
    write_json(
        output / "coverage.json",
        {"version": "v3", "byRole": role_counts, "fieldCountsAreObservationCounts": True},
    )
    graph_manifest = json.loads((output / "graph-manifest.json").read_text())
    graph_manifest.update(
        format="uk-research-graph-quality-v3",
        parentVersion=str(base.resolve()),
        qualityReport="quality-report.json",
        researchAssumption=assumption,
    )
    write_json(output / "graph-manifest.json", graph_manifest)
    for relative in [
        "scripts/repair_uk_research_data.py",
        "scripts/uk_financials/facts.py",
        "scripts/uk_financials/basic.py",
        "scripts/uk_financials/quality.py",
        "scripts/uk_financials/countries.py",
    ]:
        destination = output / "code" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / relative, destination)
    write_json(output / "repair-progress.json", {"stage": "reparsed_and_joined", **counters})
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(args.base, args.output, args.workers)
