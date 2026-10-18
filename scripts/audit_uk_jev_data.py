"""Read-only audit of the exact UK Jev inputs against labels, filing evidence and facts."""

import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
from array import array
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from prepare_uk_decisions import QUESTION
from run_uk_jevforge import calibration_lines

METRICS = (
    "assets",
    "fixed_assets",
    "current_assets",
    "current_liabilities",
    "noncurrent_liabilities",
    "net_current_assets",
    "total_assets_less_current_liabilities",
    "cash",
    "stocks",
    "debtors",
    "net_assets",
    "equity",
    "revenue",
    "profit_loss",
    "operating_profit_loss",
    "profit_before_tax",
    "average_employees",
)
FLOWS = {
    "revenue",
    "profit_loss",
    "operating_profit_loss",
    "profit_before_tax",
    "average_employees",
}
PRIMARY = {
    "Compulsory Liquidation",
    "Creditors Voluntary Liquidation",
    "In Administration",
    "Corporate Voluntary Arrangement",
    "Administrative Receiver",
}


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def json_lines(path):
    with gzip.open(path, "rt") if path.suffix == ".gz" else path.open() as stream:
        for line in stream:
            yield json.loads(line)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def shifted(month, offset):
    year, number = map(int, month.split("-"))
    year, index = divmod(year * 12 + number - 1 + offset, 12)
    return f"{year:04d}-{index + 1:02d}"


def month_end(month):
    year, number = map(int, month.split("-"))
    return f"{month}-{calendar.monthrange(year, number)[1]:02d}"


def source_amount(fact):
    text = fact["source_text"].strip().replace("\u00a0", "").replace(" ", "")
    form = fact["format"].rsplit(":", 1)[-1].lower()
    if text in {"-", "—", "–"}:
        if form not in {"zerodash", "numdash"}:
            raise ValueError("Dash without a zero-dash transform")
        text = "0"
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    if form in {"numcommadecimal", "num-comma-decimal", "numdotcomma"}:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    number = Decimal(text) * Decimal(10) ** int(fact["scale"])
    return -abs(number) if negative or fact["sign"] == "-" else number


def close(value, expected):
    if value == "":
        return expected is None
    if expected is None:
        return False
    actual = Decimal(value)
    return actual.is_finite() and abs(actual - expected) <= max(1, abs(expected)) * Decimal("1e-20")


def comparable(metric, current, previous):
    if metric not in current["values"] or metric not in previous["values"]:
        return False
    if metric != "average_employees" and current["currency"] != previous["currency"]:
        return False
    a, b = date.fromisoformat(current["end"]), date.fromisoformat(previous["end"])
    if not 330 <= (a - b).days <= 400:
        return False
    if metric in FLOWS:
        sa, sb = current["starts"].get(metric), previous["starts"].get(metric)
        if not sa or not sb:
            return False
        sa, sb = date.fromisoformat(sa), date.fromisoformat(sb)
        da, db = (a - sa).days + 1, (b - sb).days + 1
        return 330 <= da <= 400 and 330 <= db <= 400 and abs(da - db) <= 31 and b < sa
    return True


def expected_state(row, contract):
    result = {}
    for name in contract["numericFeatureAllowlist"]:
        if name.endswith("_missing") and name != "financial_missing":
            continue
        value = row[name]
        if not value:
            continue
        if value in {"True", "False"}:
            result[name] = value == "True"
        else:
            number = float(Decimal(value))
            if not math.isfinite(number):
                raise ValueError("Nonfinite input: " + name)
            result[name] = int(number) if number.is_integer() else number
    result.update({k: row[k] for k in contract["categoricalFeatureAllowlist"] if row[k]})
    return result


def state_hash(value):
    data = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


class Audit:
    def __init__(self, output):
        output.mkdir(exist_ok=False)
        self.output, self.started = output, time.perf_counter()
        self.checked, self.errors, self.warnings = Counter(), Counter(), Counter()
        self.stream = (output / "issues.csv").open("w", encoding="utf-8-sig", newline="")
        self.writer = csv.DictWriter(
            self.stream,
            fieldnames=[
                "severity",
                "code",
                "partition",
                "sample_id",
                "company_id",
                "report_id",
                "detail",
            ],
        )
        self.writer.writeheader()

    def issue(self, code, row=None, detail="", severity="error"):
        (self.errors if severity == "error" else self.warnings)[code] += 1
        row = row or {}
        self.writer.writerow(
            {
                "severity": severity,
                "code": code,
                "partition": row.get("partition", ""),
                "sample_id": row.get("sample_id", ""),
                "company_id": row.get("company_id", ""),
                "report_id": row.get("report_id", row.get("baseline_report_id", "")),
                "detail": str(detail),
            }
        )

    def check(self, code, condition, row=None, detail=""):
        self.checked[code] += 1
        if not condition:
            self.issue(code, row, detail)

    def stage(self, name, **counts):
        self.stream.flush()
        write(
            self.output / "status.json",
            {"stage": name, "elapsed_s": time.perf_counter() - self.started, **counts},
        )
        print(name, counts, flush=True)


def label_audit(audit, source, events_zip, raw_events):
    first, first_any = {}, {}
    with ZipFile(raw_events) as archive:
        name = next(
            n for n in archive.namelist() if n.startswith("Record-level") and n.endswith(".csv")
        )
        with io.TextIOWrapper(archive.open(name), encoding="latin1", newline="") as stream:
            for event in csv.DictReader(stream):
                company = event["company_number"].strip().upper()
                if company.isdigit() and len(company) <= 8:
                    company = company.zfill(8)
                if not re.fullmatch(r"(?:[0-9]{8}|[A-Z]{2}[0-9]{6})", company):
                    continue
                month = event["month_registered"]
                first_any[company] = min(first_any.get(company, "9999-99"), month)
                if event["case_type"] in PRIMARY and event["is_bulk"] != "Y":
                    first[company] = min(first.get(company, "9999-99"), month)
    with ZipFile(events_zip) as archive:
        report_name = next(n for n in archive.namelist() if n.endswith("/report.json"))
        event_report = json.loads(archive.read(report_name))
        audit.check(
            "official_event_archive_digest",
            digest(raw_events) == event_report["sourceArchiveSha256"],
        )
        name = next(n for n in archive.namelist() if n.endswith("/events.csv"))
        with io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="") as stream:
            events = {r["event_id"]: r for r in csv.DictReader(stream)}
    labels, pairs, counts = {}, defaultdict(list), Counter()
    for row in rows(source / "labels.csv"):
        sid, company, month = row["sample_id"], row["company_id"], row["observation_month"]
        audit.check("unique_sample_label", sid not in labels, row)
        labels[sid] = row
        pairs[row["pair_id"]].append(row)
        positive = row["label"] == "1"
        meaning = (
            "first_observed_primary_formal_insolvency"
            if positive
            else "no_event_observed_in_official_source_through_horizon"
        )
        audit.check("label_definition", row["label_meaning"] == meaning, row)
        audit.check(
            "twelve_month_followup",
            row["prediction_horizon_months"] == "12"
            and row["followup_start_month"] == shifted(month, 1)
            and row["followup_end_month"] == shifted(month, 12)
            and row["followup_end_month"] <= row["event_source_coverage_end"],
            row,
        )
        audit.check(
            "role_matches_label",
            row["label"] in {"0", "1"} and row["role"] == ("case" if positive else "control"),
            row,
        )
        if positive:
            audit.check(
                "positive_first_primary_month",
                first.get(company) == row["target_event_month"] == row["followup_end_month"],
                row,
            )
            # Event evidence uses semicolons; feature audit lists use pipes.
            ids = row["event_evidence_ids"].split(";")
            audit.check(
                "positive_evidence",
                bool(ids)
                and all(
                    i in events
                    and events[i]["company_id"] == company
                    and events[i]["reference_month"] == row["target_event_month"]
                    and events[i]["label_candidate"] == "True"
                    and events[i]["is_first_observed_month"] == "True"
                    for i in ids
                ),
                row,
            )
        else:
            audit.check(
                "negative_no_recorded_event_through_followup",
                first_any.get(company, "9999-99") > row["followup_end_month"],
                row,
            )
            counts["controls_with_later_recorded_event"] += company in first_any
        counts["label:" + row["label"]] += 1
    for pair in pairs.values():
        audit.check(
            "matched_pair",
            len(pair) == 2
            and {r["label"] for r in pair} == {"0", "1"}
            and len({r["company_id"] for r in pair}) == 2
            and len({r["observation_month"] for r in pair}) == 1,
            pair[0],
        )
    return labels, counts


def history_audit(audit, source):
    sources, histories, baselines, counts = {}, {}, {}, Counter()
    for row in rows(source / "financial-report-sources.csv"):
        rid = row["report_id"]
        audit.check("unique_report_source", rid not in sources, row)
        audit.check(
            "assumed_availability_formula",
            row["availability_upper_bound"] == month_end(shifted(row["filing_month"], 1)),
            row,
        )
        audit.check(
            "report_period_before_availability",
            row["period_end"] <= row["availability_upper_bound"],
            row,
        )
        sources[rid] = (row["company_id"], row["period_end"], row["availability_upper_bound"])
        counts["reports"] += 1
        counts["exact_filing_dates_verified"] += row["filing_date_exact_verified"] == "True"
    for row in rows(source / "financial-history.csv"):
        hid, rid = row["history_id"], row["report_id"]
        audit.check("unique_history", hid not in histories, row)
        report = sources[rid]
        audit.check(
            "history_source_identity_time",
            row["company_id"] == report[0]
            and row["report_period_end"] == report[1]
            and row["available_by_assumed"] == report[2]
            and row["period_end"] <= report[1],
            row,
        )
        values = {k: row[k] for k in METRICS if row[k]}
        histories[hid] = {
            "report": rid,
            "company": row["company_id"],
            "end": row["period_end"],
            "available": report[2],
            "currency": row["financial_currency"],
            "values": values,
            "starts": {k: row[k + "_period_start"] for k in FLOWS if row[k + "_period_start"]},
        }
        audit.check("history_metric_count", len(values) == int(row["accepted_metric_count"]), row)
        if row["period_kind"] == "current":
            baselines[rid] = histories[hid]
        counts["history_rows"] += 1
    masks = Counter()
    for i, fact in enumerate(json_lines(source / "history-facts.jsonl.gz"), 1):
        h, metric = histories[fact["history_id"]], fact["metric"]
        bit = 1 << METRICS.index(metric)
        audit.check("fact_unique_metric", not masks[fact["history_id"]] & bit, fact)
        masks[fact["history_id"]] |= bit
        audit.check(
            "fact_identity_period_value",
            fact["report_id"] == h["report"]
            and fact["company_id"] == h["company"]
            and fact["period_end"] == h["end"]
            and fact["value"] == h["values"].get(metric),
            fact,
        )
        audit.check(
            "fact_unit",
            fact["unit"] == ("pure" if metric == "average_employees" else h["currency"]),
            fact,
        )
        try:
            actual = Decimal(fact["value"])
            audit.check(
                "fact_scale_sign_transform",
                actual.is_finite() and source_amount(fact) == actual,
                fact,
            )
            if metric == "average_employees":
                accepted = (
                    0 <= actual <= 100000
                    and int(fact["scale"]) == 0
                    and not (h["company"].isdigit() and actual == int(h["company"]))
                )
            else:
                accepted = fact["unit"] not in {"GBP", "EUR", "USD"} or abs(actual) < Decimal(
                    "1e11"
                )
            audit.check("all_accepted_facts_meet_quarantine_policy", accepted, fact)
        except (ValueError, ArithmeticError) as exc:
            audit.check("fact_scale_sign_transform", False, fact, exc)
        counts["accepted_facts"] += 1
        counts["unit:" + fact["unit"]] += 1
        counts["scale:" + fact["scale"]] += 1
        if i % 400000 == 0:
            audit.stage("facts", checked=i)
    for hid, h in histories.items():
        audit.check("facts_cover_history", masks[hid].bit_count() == len(h["values"]))
    issue_counts, warned = Counter(), set()
    for issue in json_lines(source / "history-quality-issues.jsonl.gz"):
        issue_counts[issue["action"] + ":" + issue["reason"]] += 1
        if issue["action"] == "quarantine":
            audit.check(
                "quarantined_metric_not_accepted",
                issue["metric"] not in histories[issue["history_id"]]["values"],
                issue,
            )
        else:
            warned.add(issue["history_id"])
    return histories, baselines, counts, issue_counts, warned


def check_trends(audit, row, current, selected):
    by_end = {h["end"]: h for h in selected}
    for metric in METRICS:
        audit.check(
            "baseline_value_from_source",
            row[metric] == current["values"].get(metric, ""),
            row,
            metric,
        )
        candidates = [h for h in selected[1:] if metric in h["values"]]
        eligible = [h for h in candidates if comparable(metric, current, h)]
        prior = next(iter(eligible or candidates), None)
        audit.check(
            "previous_value_and_unit",
            row[metric + "_previous"] == (prior["values"][metric] if prior else "")
            and row[metric + "_previous_period_end"] == (prior["end"] if prior else "")
            and row[metric + "_previous_unit"]
            == (("pure" if metric == "average_employees" else prior["currency"]) if prior else ""),
            row,
            metric,
        )
        delta, growth = None, None
        if eligible:
            delta = Decimal(row[metric]) - Decimal(prior["values"][metric])
            if Decimal(prior["values"][metric]) > 0:
                growth = delta / Decimal(prior["values"][metric])
        audit.check(
            "delta_comparability_and_arithmetic", close(row[metric + "_delta"], delta), row, metric
        )
        audit.check(
            "growth_positive_base_and_arithmetic",
            close(row[metric + "_relative_change"], growth),
            row,
            metric,
        )
        slope = row[metric + "_three_period_slope_per_year"]
        if slope:
            ends = row[metric + "_slope_period_ends"].split("|")
            triple = [by_end[end] for end in ends]
            audit.check(
                "slope_comparable_periods",
                len(triple) == 3
                and comparable(metric, triple[0], triple[1])
                and comparable(metric, triple[1], triple[2]),
                row,
                metric,
            )
            x = [Decimal((date.fromisoformat(e) - date.fromisoformat(ends[-1])).days) for e in ends]
            y = [Decimal(h["values"][metric]) for h in triple]
            expected = (
                (3 * sum(a * b for a, b in zip(x, y, strict=True)) - sum(x) * sum(y))
                / (3 * sum(a * a for a in x) - sum(x) ** 2)
                * Decimal("365.25")
            )
            audit.check("slope_arithmetic", close(slope, expected), row, metric)
    for name, numerator in [("current_ratio", "current_assets"), ("cash_ratio", "cash")]:

        def ratio(h, numerator=numerator):
            v = h["values"] if h else {}
            if numerator not in v or Decimal(v.get("current_liabilities", "0")) <= 0:
                return None
            return Decimal(v[numerator]) / Decimal(v["current_liabilities"])

        now, before = ratio(current), by_end.get(row[name + "_previous_period_end"])
        previous = ratio(before)
        audit.check("ratio_positive_denominator", close(row[name], now), row, name)
        audit.check("previous_ratio", close(row[name + "_previous"], previous), row, name)
        if row[name + "_delta"]:
            audit.check(
                "ratio_delta",
                now is not None
                and previous is not None
                and close(row[name + "_delta"], now - previous),
                row,
                name,
            )


def audit_dataset(args):
    audit = Audit(args.output)
    source, decisions = args.source, args.decisions
    delivery = json.loads((source / "delivery-manifest.json").read_text())
    for name, info in delivery["files"].items():
        path = source / name
        audit.check(
            "source_manifest",
            path.is_file()
            and path.stat().st_size == info["bytes"]
            and digest(path) == info["sha256"],
            detail=name,
        )
    manifest = json.loads((decisions / "manifest.json").read_text())
    for name, info in manifest["files"].items():
        path = decisions / name
        audit.check("decision_manifest", digest(path) == info["sha256"], detail=name)
    trained = json.loads((args.trained / "results/config.json").read_text())
    audit.check(
        "exact_trained_data_manifest",
        digest(decisions / "manifest.json") == trained["source_manifest_sha256"],
    )
    index = list(json_lines(decisions / "sample-index.jsonl"))
    calibration = calibration_lines([r for r in index if r["split"] == "train"])
    selected = {
        r["sample_id"]: {
            **r,
            "partition": ("calibration" if r["line"] in calibration else "train")
            if r["split"] == "train"
            else r["split"],
        }
        for r in index
    }
    audit.check("unique_decision_index", len(index) == len(selected))
    labels, label_counts = label_audit(audit, source, args.events, args.raw_events)
    partition_counts = Counter()
    for sid, row in selected.items():
        label = labels[sid]
        audit.check(
            "index_matches_label",
            all(
                row[k] == label[k]
                for k in [
                    "company_id",
                    "pair_id",
                    "observation_month",
                    "followup_end_month",
                ]
            ),
            row,
        )
        row["gold"] = int(label["label"])
        partition_counts[row["partition"]] += 1
        if label["case_event_review_reasons"]:
            audit.issue("event_source_review", row, label["case_event_review_reasons"], "review")
    for name, count in partition_counts.items():
        audit.check("trained_partition_count", count == trained["groups"][name]["n"], detail=name)
    for left, right in [
        ("train", "calibration"),
        ("train", "valid"),
        ("train", "test"),
        ("calibration", "valid"),
        ("calibration", "test"),
        ("valid", "test"),
    ]:
        for key in ["company_id", "pair_id"]:
            a = {r[key] for r in selected.values() if r["partition"] == left}
            b = {r[key] for r in selected.values() if r["partition"] == right}
            audit.check("partition_isolation", not a & b, detail=f"{left}/{right}/{key}")
    audit.stage("labels_verified", samples=len(labels), decisions=len(selected))
    histories, baselines, fact_counts, quality_counts, warned = history_audit(audit, source)
    links = defaultdict(list)
    for row in rows(source / "sample-history-links.csv"):
        if row["sample_id"] in selected:
            links[row["sample_id"]].append(row)
    contract = json.loads((source / "feature-contract.json").read_text())
    expected_hashes, statistics = {}, defaultdict(lambda: array("d"))
    coverage, time_margins = Counter(), defaultdict(list)
    for i, row in enumerate(rows(source / "features.csv"), 1):
        sid = row["sample_id"]
        if sid not in selected:
            continue
        info = selected[sid]
        row["partition"] = info["partition"]
        group, gold = info["partition"], str(info["gold"])
        current = baselines[row["baseline_report_id"]]
        audit.check(
            "feature_label_identity_date",
            row["company_id"] == info["company_id"]
            and row["observation_date"] == month_end(info["observation_month"]),
            row,
        )
        picked = links[sid]
        audit.check("history_link_count", len(picked) == int(row["financial_period_count"]), row)
        chosen = []
        for link in picked:
            history = histories[link["history_id"]]
            audit.check(
                "no_future_disclosure_under_assumption",
                history["available"]
                == link["available_by_assumed"]
                <= current["available"]
                <= row["observation_date"],
                row,
            )
            audit.check(
                "history_link_identity",
                history["company"] == row["company_id"]
                and history["report"] == link["report_id"]
                and history["end"] == link["period_end"] <= current["end"],
                row,
            )
            chosen.append(history)
        check_trends(audit, row, current, chosen)
        audit.check(
            "report_age",
            int(row["report_age_days"])
            == (
                date.fromisoformat(row["observation_date"]) - date.fromisoformat(current["end"])
            ).days,
            row,
        )
        margin = (
            date.fromisoformat(row["observation_date"]) - date.fromisoformat(current["available"])
        ).days
        time_margins[group].append(margin)
        state = expected_state(row, contract)
        expected_hashes[sid] = state_hash(state)
        coverage[group, gold, "samples"] += 1
        coverage[group, gold, "financial_missing"] += bool(state.get("financial_missing"))
        coverage[group, gold, "currency:" + state.get("financial_currency", "missing")] += 1
        coverage[group, gold, "report_age_above_730_days"] += int(row["report_age_days"]) > 730
        coverage[group, gold, "baseline_quality_warning"] += bool(row["financial_quality_warnings"])
        coverage[group, gold, "linked_history_warning"] += any(
            link["history_id"] in warned for link in picked
        )
        for metric in METRICS:
            coverage[group, gold, "observed:" + metric] += metric in state
        for name, value in state.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                statistics[group, name].append(value)
                if name in METRICS and name != "average_employees":
                    audit.check(
                        "accepted_amount_policy",
                        not (current["currency"] in {"GBP", "EUR", "USD"} and abs(value) >= 1e11),
                        row,
                        name,
                    )
                if name == "average_employees":
                    audit.check(
                        "accepted_employee_policy",
                        0 <= value <= 100000
                        and not (row["company_id"].isdigit() and value == int(row["company_id"])),
                        row,
                    )
                if (
                    name.endswith("_relative_change")
                    and abs(value) > 100
                    or name in {"current_ratio", "cash_ratio"}
                    and abs(value) > 100
                ):
                    audit.issue("large_ratio_review", row, f"{name}={value}", "review")
        if row["financial_quality_warnings"]:
            audit.issue("baseline_quality_review", row, row["financial_quality_warnings"], "review")
        if i % 20000 == 0:
            audit.stage("features", source_rows=i, selected_rows=len(expected_hashes))
    for split in ["train", "valid", "test"]:
        split_index = [r for r in index if r["split"] == split]
        for number, item in enumerate(json_lines(decisions / f"{split}.financial.jsonl")):
            indexed = split_index[number]
            sid = indexed["sample_id"]
            audit.check("jsonl_index_line", indexed["line"] == number + 1, indexed)
            audit.check(
                "actual_model_input_matches_source",
                set(item["state"]) == {"features"}
                and state_hash(item["state"]["features"]) == expected_hashes[sid],
                indexed,
            )
            audit.check(
                "actual_model_label",
                item["expected"]
                == {"formal_insolvency_12m": "event" if selected[sid]["gold"] else "no_event"},
                indexed,
            )
            audit.check(
                "fixed_question_template",
                item["questions"]
                == {
                    "formal_insolvency_12m": QUESTION,
                },
                indexed,
            )
        audit.check("jsonl_row_count", number + 1 == len(split_index), detail=split)
    distributions = []
    for (group, name), values in sorted(statistics.items()):
        ordered = sorted(values)
        distributions.append(
            {
                "partition": group,
                "feature": name,
                "n": len(values),
                "missing": partition_counts[group] - len(values),
                "zero": sum(x == 0 for x in values),
                "negative": sum(x < 0 for x in values),
                "min": ordered[0],
                "median": ordered[(len(values) - 1) // 2],
                "p99": ordered[int((len(values) - 1) * 0.99)],
                "max": ordered[-1],
            }
        )
    for name, records in [
        ("feature-distributions.csv", distributions),
        (
            "coverage.csv",
            [
                {"partition": g, "label": y, "measure": k, "count": v}
                for (g, y, k), v in sorted(coverage.items())
            ],
        ),
    ]:
        with (args.output / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    result = {
        "passed_hard_checks": not audit.errors,
        "source": str(source.resolve()),
        "decisions": str(decisions.resolve()),
        "partitions": partition_counts,
        "label_source_counts": label_counts,
        "fact_counts": fact_counts,
        "history_quality_issues": quality_counts,
        "checks": audit.checked,
        "errors": audit.errors,
        "reviews": audit.warnings,
        "availability": {
            "exact_verified_reports": fact_counts["exact_filing_dates_verified"],
            "assumption": "Filing month +1 month-end; publication date unverified",
            "minimum_margin_days": {g: min(v) for g, v in time_margins.items()},
        },
        "limitations": [
            "First observed in source history, not proven first ever",
            "Negative: no recorded event through followup; not confirmed healthy",
            "Matched 1:1 sample prevalence is not population risk",
            "Exact filing dates and historical registry unverified",
            "Raw HTML not reparsed; delivered facts and hashes checked",
        ],
        "audit_script_sha256": digest(Path(__file__)),
        "elapsed_s": time.perf_counter() - audit.started,
    }
    write(args.output / "summary.json", result)
    audit.stage("complete", passed=not audit.errors)
    audit.stream.close()
    print(json.dumps(result, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("datasets/uk_research"))
    parser.add_argument("--decisions", type=Path, default=Path("datasets/uk_decisions_20261018"))
    parser.add_argument("--trained", type=Path, default=Path("datasets/uk_financial_full_20261018"))
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("datasets/archive/uk-research-20261017/uk-adverse-events-2020-2025-v1.zip"),
    )
    parser.add_argument(
        "--raw-events",
        type=Path,
        default=Path("datasets/sources/insolvency-service-2025-12/record-level.zip"),
    )
    parser.add_argument("--output", type=Path, required=True)
    audit_dataset(parser.parse_args())


if __name__ == "__main__":
    main()
