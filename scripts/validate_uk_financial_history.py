"""Check history/source joins and trend arithmetic independently of the feature builder."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from itertools import groupby, zip_longest
from pathlib import Path

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from repair_uk_research_data import json_lines
from uk_financials.facts import ALIASES

FLOW_NAMES = {
    "revenue",
    "profit_loss",
    "operating_profit_loss",
    "profit_before_tax",
    "average_employees",
}


def comparable(metric, current, previous):
    if metric not in current["values"] or metric not in previous["values"]:
        return False
    if metric != "average_employees" and current["currency"] != previous["currency"]:
        return False
    if (
        not 330
        <= (date.fromisoformat(current["end"]) - date.fromisoformat(previous["end"])).days
        <= 400
    ):
        return False
    if metric in FLOW_NAMES:
        try:
            end_a, end_b = date.fromisoformat(current["end"]), date.fromisoformat(previous["end"])
            start_a, start_b = (
                date.fromisoformat(current["starts"][metric]),
                date.fromisoformat(previous["starts"][metric]),
            )
        except (ValueError, KeyError):
            return False
        lengths = (end_a - start_a).days + 1, (end_b - start_b).days + 1
        return (
            all(330 <= n <= 400 for n in lengths)
            and abs(lengths[0] - lengths[1]) <= 31
            and end_b < start_a
        )
    return True


def equal_number(value, expected):
    assert value != ""
    observed = Decimal(value)
    assert observed.is_finite()
    assert abs(observed - expected) <= max(Decimal(1), abs(expected)) * Decimal("1e-20"), (
        value,
        expected,
    )


def validate(base, output):
    report = json.loads((output / "history-report.json").read_text())
    assert report["baseDeliverySha256"] == sha(base / "delivery-manifest.json")
    for name, digest in report["inputFiles"].items():
        assert sha(base / name) == digest
    assert sha(base / "labels.csv") == sha(output / "labels.csv")
    assert (
        not report["exactFilingDatesVerified"]
        and not report["externalApiOrRelationshipCollectionPerformed"]
    )
    sources = {}
    for row in read_csv(output / "financial-report-sources.csv"):
        rid = row["report_id"]
        assert (
            rid not in sources
            and not row["filing_date_exact"]
            and row["filing_date_exact_verified"] == "False"
        )
        sources[rid] = {
            "company": row["company_id"],
            "end": row["period_end"],
            "available": row["availability_upper_bound"],
            "sha": row["member_sha256"],
            "crc": row["member_crc32"],
            "size": row["member_size"],
        }
    baseline_ids = set()
    for row in json_lines(base / "historical-basic-profiles.jsonl.gz"):
        source = sources[row["report_id"]]
        assert (
            source["company"],
            source["end"],
            source["available"],
            source["sha"],
            source["crc"],
            source["size"],
        ) == tuple(
            str(row[key])
            for key in [
                "company_id",
                "period_end",
                "availability_upper_bound",
                "member_sha256",
                "member_crc32",
                "member_size",
            ]
        )
        baseline_ids.add(row["report_id"])
    assert len(baseline_ids) == 208853
    histories, by_company, current_rows = {}, defaultdict(list), {}
    counts = Counter()
    for row in read_csv(output / "financial-history.csv"):
        hid, rid = row["history_id"], row["report_id"]
        assert hid not in histories
        assert hid == hashlib.sha256((rid + "|" + row["period_end"]).encode()).hexdigest()
        source = sources[rid]
        assert row["company_id"] == source["company"] and row["report_period_end"] == source["end"]
        assert (
            row["available_by_assumed"] == source["available"]
            and row["period_end"] <= source["end"]
        )
        values = {metric: row[metric] for metric in ALIASES if row[metric] != ""}
        assert int(row["accepted_metric_count"]) == len(values)
        for metric in ALIASES:
            assert row[metric + "_missing"] == str(row[metric] == "")
        monetary = any(metric != "average_employees" for metric in values)
        assert row["financial_missing"] == str(not monetary)
        assert bool(row["financial_currency"]) == monetary
        compact = {
            "id": hid,
            "company": row["company_id"],
            "report": rid,
            "report_end": source["end"],
            "end": row["period_end"],
            "available": source["available"],
            "currency": row["financial_currency"],
            "values": values,
            "starts": {
                metric: row[metric + "_period_start"]
                for metric in FLOW_NAMES
                if row[metric + "_period_start"]
            },
        }
        histories[hid] = compact
        by_company[row["company_id"]].append(compact)
        if row["period_kind"] == "current":
            assert row["period_end"] == source["end"] and rid not in current_rows
            current_rows[rid] = compact
        else:
            assert row["period_kind"] == "comparative" and row["period_end"] < source["end"]
        counts["historyRows"] += 1
    assert current_rows.keys() == sources.keys()
    bit = {metric: 1 << index for index, metric in enumerate(ALIASES)}
    seen_masks, quarantined = Counter(), Counter()
    for fact in json_lines(output / "history-facts.jsonl.gz"):
        hid, metric = fact["history_id"], fact["metric"]
        row = histories[hid]
        assert fact["report_id"] == row["report"] and fact["company_id"] == row["company"]
        assert fact["period_end"] == row["end"] and fact["value"] == row["values"][metric]
        assert fact["unit"] == ("pure" if metric == "average_employees" else row["currency"])
        assert Decimal(fact["value"]).is_finite()
        assert not seen_masks[hid] & bit[metric]
        seen_masks[hid] |= bit[metric]
        counts["acceptedFacts"] += 1
    for hid, row in histories.items():
        assert seen_masks[hid].bit_count() == len(row["values"])
    for issue in json_lines(output / "history-quality-issues.jsonl.gz"):
        if issue["action"] == "quarantine":
            assert issue["metric"] not in histories[issue["history_id"]]["values"]
            quarantined[issue["history_id"]] |= bit[issue["metric"]]
    source_masks = Counter()
    for fact in json_lines(output / "history-source-facts.jsonl.gz"):
        hid, metric = fact["history_id"], fact["metric"]
        assert not source_masks[hid] & bit[metric]
        source_masks[hid] |= bit[metric]
        assert (seen_masks[hid] | quarantined[hid]) & bit[metric]
        if seen_masks[hid] & bit[metric]:
            assert histories[hid]["values"][metric] == fact["value"]
    for hid in histories:
        assert source_masks[hid] == (seen_masks[hid] | quarantined[hid])
    groups = groupby(
        read_csv(output / "sample-history-links.csv"), key=lambda row: row["sample_id"]
    )
    samples = set()
    for old, row, grouped in zip_longest(
        read_csv(base / "features.csv"), read_csv(output / "features.csv"), groups
    ):
        assert old and row and grouped
        assert all(row[key] == value for key, value in old.items())
        sid, links_iter = grouped
        assert sid == row["sample_id"] and sid not in samples
        samples.add(sid)
        links = list(links_iter)
        baseline = current_rows[row["baseline_report_id"]]
        selected = []
        for index, link in enumerate(links):
            history = histories[link["history_id"]]
            assert link["company_id"] == history["company"] == row["company_id"]
            assert (
                link["observation_date"] == row["observation_date"]
                and link["baseline_report_id"] == row["baseline_report_id"]
            )
            assert int(link["period_rank"]) == index
            assert link["period_end"] == history["end"] and link["report_id"] == history["report"]
            assert (
                link["available_by_assumed"]
                == history["available"]
                <= baseline["available"]
                <= row["observation_date"]
            )
            assert history["end"] <= baseline["end"] and history["report_end"] <= baseline["end"]
            selected.append(history)
        assert selected[0]["id"] == baseline["id"]
        assert len({history["end"] for history in selected}) == len(selected)
        assert [history["end"] for history in selected] == sorted(
            (history["end"] for history in selected), reverse=True
        )
        expected = {baseline["end"]: baseline}
        for candidate in by_company[row["company_id"]]:
            if (
                not candidate["values"]
                or candidate["available"] > baseline["available"]
                or candidate["end"] >= baseline["end"]
                or candidate["report_end"] > baseline["end"]
            ):
                continue
            previous = expected.get(candidate["end"])

            def priority(entry, baseline_report=baseline["report"]):
                return (
                    entry["report"] == baseline_report,
                    entry["available"],
                    entry["report_end"],
                    entry["report"],
                )

            if previous is None or priority(candidate) > priority(previous):
                expected[candidate["end"]] = candidate
        assert {history["id"] for history in selected} == {
            history["id"] for history in expected.values()
        }
        assert int(row["financial_period_count"]) == len(selected)
        assert int(row["financial_comparative_period_count"]) == len(selected) - 1
        by_end = {history["end"]: history for history in selected}
        for metric in ALIASES:
            assert row[metric] == baseline["values"].get(metric, "")
            candidates = [history for history in selected[1:] if metric in history["values"]]
            eligible = [history for history in candidates if comparable(metric, baseline, history)]
            prior = next(iter(eligible or candidates), None)
            assert row[metric + "_previous"] == (prior["values"][metric] if prior else "")
            assert row[metric + "_previous_period_end"] == (prior["end"] if prior else "")
            if eligible:
                delta = Decimal(baseline["values"][metric]) - Decimal(prior["values"][metric])
                equal_number(row[metric + "_delta"], delta)
                if Decimal(prior["values"][metric]) > 0:
                    equal_number(
                        row[metric + "_relative_change"], delta / Decimal(prior["values"][metric])
                    )
                else:
                    assert row[metric + "_relative_change"] == ""
            else:
                assert row[metric + "_delta"] == "" and row[metric + "_relative_change"] == ""
            slope = row[metric + "_three_period_slope_per_year"]
            older = [
                history
                for history in selected
                if prior and history["end"] < prior["end"] and comparable(metric, prior, history)
            ]
            assert bool(slope) == bool(eligible and older)
            if slope:
                ends = row[metric + "_slope_period_ends"].split("|")
                assert ends == [baseline["end"], prior["end"], older[0]["end"]]
                triple = [by_end[end] for end in ends]
                x = [
                    Decimal((date.fromisoformat(end) - date.fromisoformat(ends[2])).days)
                    for end in ends
                ]
                y = [Decimal(entry["values"][metric]) for entry in triple]
                expected_slope = (
                    (3 * sum(a * b for a, b in zip(x, y, strict=True)) - sum(x) * sum(y))
                    / (3 * sum(a * a for a in x) - sum(x) ** 2)
                    * Decimal("365.25")
                )
                equal_number(slope, expected_slope)
            for suffix in ["previous", "delta", "relative_change", "three_period_slope_per_year"]:
                assert row[f"{metric}_{suffix}_missing"] == str(row[f"{metric}_{suffix}"] == "")
        for name, numerator in [("current_ratio", "current_assets"), ("cash_ratio", "cash")]:

            def value(entry, numerator=numerator):
                if (
                    numerator not in entry["values"]
                    or Decimal(entry["values"].get("current_liabilities", "0")) <= 0
                ):
                    return None
                return Decimal(entry["values"][numerator]) / Decimal(
                    entry["values"]["current_liabilities"]
                )

            now = value(baseline)
            before = by_end.get(row[name + "_previous_period_end"])
            prior_value = value(before) if before else None
            if now is not None:
                equal_number(row[name], now)
            else:
                assert row[name] == ""
            if prior_value is not None:
                equal_number(row[name + "_previous"], prior_value)
            else:
                assert row[name + "_previous"] == ""
            if row[name + "_delta"]:
                assert now is not None and prior_value is not None
                assert (
                    330
                    <= (
                        date.fromisoformat(baseline["end"]) - date.fromisoformat(before["end"])
                    ).days
                    <= 400
                )
                equal_number(row[name + "_delta"], now - prior_value)
        counts["samples"] += 1
        counts["samplesWithComparatives"] += len(selected) >= 2
        counts["samplesWithThreePeriods"] += len(selected) >= 3
        if counts["samples"] % 40000 == 0:
            print(f"VALIDATED {counts['samples']}/209192 samples", flush=True)
    assert counts["samples"] == 209192
    assert counts["acceptedFacts"] == report["sourceReports"]["accepted_facts"]
    result = {
        "passed": True,
        **counts,
        "sourceReports": len(sources),
        "v3BaselineReports": len(baseline_ids),
        "allBaseFeatureColumnsAndLabelsPreserved": True,
        "allComparativesUseSourceDisclosureAvailability": True,
        "unitsAnnualSpacingDurationsAndNonpositiveBasesVerified": True,
        "exactFilingDatesVerified": False,
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
