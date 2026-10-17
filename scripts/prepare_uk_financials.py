"""Supplement monthly UK adverse events with point-in-time eligible electronic accounts."""

import argparse
import calendar
import csv
import gzip
import hashlib
import json
import re
import threading
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from uk_financials.archives import TRANSFER, index_archive, member_bytes
from uk_financials.facts import ALIASES, parse_document

FILENAME = re.compile(r"_([A-Z0-9]{8})_([0-9]{8})\.(?:html|xhtml|xml|zip)$", re.I)
MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
PRINT_LOCK = threading.Lock()


def log(message):
    with PRINT_LOCK:
        print(message, flush=True)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def month_shift(month, offset):
    year, number = map(int, month.split("-"))
    absolute = year * 12 + number - 1 + offset
    return f"{absolute // 12:04d}-{absolute % 12 + 1:02d}"


def month_end(month):
    year, number = map(int, month.split("-"))
    return date(year, number, calendar.monthrange(year, number)[1]).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def document_id(entry):
    return hashlib.sha256((entry["url"] + "#" + entry["member"]).encode()).hexdigest()


def scan_month(month, targets, cache, target_digest):
    filtered = cache / "selected-indexes" / f"{month}-{target_digest[:16]}.json.gz"
    if filtered.exists():
        return json.loads(gzip.decompress(filtered.read_bytes()))
    year, number = map(int, month.split("-"))
    url = f"https://download.companieshouse.gov.uk/archive/Accounts_Monthly_Data-{MONTH_NAMES[number]}{year}.zip"
    manifest, entries = index_archive(url, cache / "indexes" / month)
    chosen = []
    for entry in entries:
        match = FILENAME.search(entry["member"])
        if not match or match[1].upper() not in targets:
            continue
        try:
            report_end = date(int(match[2][:4]), int(match[2][4:6]), int(match[2][6:])).isoformat()
        except ValueError:
            continue
        chosen.append(
            {
                **entry,
                "company_id": match[1].upper(),
                "period_end": report_end,
                "filing_month": month,
                "available_by": month_end(month_shift(month, 1)),
                "url": url,
                "archive": manifest,
            }
        )
    result = {"month": month, "manifest": manifest, "totalMembers": len(entries), "entries": chosen}
    filtered.parent.mkdir(parents=True, exist_ok=True)
    temporary = filtered.with_suffix(".part")
    temporary.write_bytes(gzip.compress(json.dumps(result).encode()))
    temporary.replace(filtered)
    return result


def fetch_facts(entry, cache, parser_sha):
    identity = document_id(entry)
    parsed_path = cache / "parsed" / parser_sha / f"{identity}.json.gz"
    if parsed_path.exists():
        cached = json.loads(gzip.decompress(parsed_path.read_bytes()))
        if cached.get("status") != "download_error":
            return cached
    source = cache / "documents" / identity[:2] / f"{identity}.gz"
    try:
        if source.exists():
            raw = gzip.decompress(source.read_bytes())
        else:
            raw = member_bytes(entry["archive"], entry)
            source.parent.mkdir(parents=True, exist_ok=True)
            temporary = source.with_suffix(".part")
            temporary.write_bytes(gzip.compress(raw))
            temporary.replace(source)
        if len(raw) != entry["size"] or zlib.crc32(raw) != entry["crc32"]:
            raise ValueError("Cached document failed original ZIP size/CRC validation")
        result = {
            "report_id": identity,
            "entry": entry,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_cache": str(source),
            "parser_sha256": parser_sha,
        }
    except Exception as error:
        return {
            "report_id": identity,
            "entry": entry,
            "status": "download_error",
            "error": str(error),
        }
    try:
        parsed = parse_document(raw, entry["company_id"], entry["period_end"])
        result.update(parsed)
        monetary = [metric for metric in parsed["facts"] if metric != "average_employees"]
        result["status"] = "parsed" if monetary else "no_supported_monetary_facts"
    except Exception as error:
        result.update(status="parse_error", error=str(error))
    parsed_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = parsed_path.with_suffix(".part")
    temporary.write_bytes(gzip.compress(json.dumps(result).encode()))
    temporary.replace(parsed_path)
    return result


def prepare(events_path, output, cache, horizon=12, lookback=36, index_workers=3, workers=12):
    output.mkdir(parents=True, exist_ok=True)
    with events_path.open(encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    if len({event["event_id"] for event in events}) != len(events):
        raise ValueError("Repeated event evidence identity")
    targets = defaultdict(set)
    for event in events:
        if event["company_id"]:
            targets[event["company_id"]].add(month_shift(event["reference_month"], -horizon))
    target_digest = hashlib.sha256(json.dumps(sorted(targets)).encode()).hexdigest()
    pairs = [
        (company, observation)
        for company, observations in targets.items()
        for observation in observations
    ]
    best = {pair: [] for pair in pairs}
    start = month_shift(min(observation for _, observation in pairs), -lookback)
    end = month_shift(max(observation for _, observation in pairs), -1)
    months = []
    current = start
    while current <= end:
        months.append(current)
        current = month_shift(current, 1)
    manifests, scan_errors = {}, {}
    log(
        f"indexing {len(months)} months {start}..{end}; "
        f"companies={len(targets)}, observations={len(pairs)}"
    )
    selection_path = output / "selection.jsonl.gz"
    selection_meta_path = output / "selection-metadata.json"
    expected_selection = {
        "selectionVersion": 1,
        "eventsSha256": sha(events_path),
        "horizon": horizon,
        "lookback": lookback,
    }
    cached = json.loads(selection_meta_path.read_text()) if selection_meta_path.exists() else {}
    reusable = (
        all(cached.get(key) == value for key, value in expected_selection.items())
        and selection_path.exists()
        and cached.get("selectionSha256") == sha(selection_path)
        and (output / "archive-manifests.json").exists()
        and cached.get("manifestsSha256") == sha(output / "archive-manifests.json")
    )
    if reusable:
        with gzip.open(selection_path, "rt") as stream:
            best = {
                (row["company_id"], row["observation_month"]): row["entries"]
                for row in map(json.loads, stream)
            }
        manifests = json.loads((output / "archive-manifests.json").read_text())
        if set(best) != set(pairs) or set(manifests) != set(months):
            raise ValueError("Cached selection has a different target or archive range")
        log(f"reused validated selection cache for {len(best)} company/observation pairs")
    else:
        with ThreadPoolExecutor(max_workers=index_workers) as pool:
            futures = {
                pool.submit(scan_month, month, targets, cache, target_digest): month
                for month in reversed(months)
            }
            for future in as_completed(futures):
                month = futures[future]
                try:
                    result = future.result()
                    manifests[month] = {
                        **result["manifest"],
                        "totalMembers": result["totalMembers"],
                    }
                    for entry in result["entries"]:
                        for observation in targets[entry["company_id"]]:
                            if (
                                entry["available_by"] > month_end(observation)
                                or entry["filing_month"] < month_shift(observation, -lookback)
                                or entry["period_end"] > month_end(observation)
                            ):
                                continue
                            group = best[entry["company_id"], observation]
                            group.append(entry)
                            group.sort(
                                key=lambda e: (e["period_end"], e["filing_month"], e["member"]),
                                reverse=True,
                            )
                            del group[3:]
                    log(
                        f"INDEX {month} members={result['totalMembers']} "
                        f"target_files={len(result['entries'])} done={len(manifests)}/{len(months)}"
                    )
                except Exception as error:
                    scan_errors[month] = str(error)
                    log(f"INDEX_ERROR {month} {error}")
                write_json(
                    output / "progress.json",
                    {
                        "stage": "index",
                        "monthsDone": len(manifests),
                        "monthsExpected": len(months),
                        "indexErrors": scan_errors,
                        "transfer": TRANSFER,
                    },
                )
        selection = [
            {"company_id": pair[0], "observation_month": pair[1], "entries": values}
            for pair, values in sorted(best.items())
        ]
        with gzip.open(output / "selection.jsonl.gz", "wt") as stream:
            for selected in selection:
                stream.write(json.dumps(selected) + "\n")
        write_json(output / "archive-manifests.json", manifests)
        if not scan_errors:
            write_json(
                selection_meta_path,
                {
                    **expected_selection,
                    "selectionSha256": sha(selection_path),
                    "manifestsSha256": sha(output / "archive-manifests.json"),
                },
            )
    parser_sha = sha(Path(__file__).parent / "uk_financials/facts.py")
    results, selected_reports = {}, {}
    for attempt in range(3):
        wanted = {}
        for pair, entries in best.items():
            if pair not in selected_reports and len(entries) > attempt:
                entry = entries[attempt]
                wanted[document_id(entry)] = entry
        log(f"fetch round={attempt + 1} documents={len(wanted)}")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(fetch_facts, entry, cache, parser_sha): key
                for key, entry in wanted.items()
                if key not in results
            }
            done = 0
            for future in as_completed(futures):
                key = futures[future]
                results[key] = future.result()
                done += 1
                if done % 200 == 0 or done == len(futures):
                    counts = Counter(result["status"] for result in results.values())
                    log(
                        f"FETCH round={attempt + 1} done={done}/{len(futures)} "
                        f"states={dict(counts)} bytes={TRANSFER['bytes']}"
                    )
                    write_json(
                        output / "progress.json",
                        {
                            "stage": "documents",
                            "round": attempt + 1,
                            "done": done,
                            "expected": len(futures),
                            "states": dict(counts),
                            "transfer": TRANSFER,
                        },
                    )
        for pair, entries in best.items():
            if pair not in selected_reports and len(entries) > attempt:
                result = results[document_id(entries[attempt])]
                if result["status"] == "parsed":
                    selected_reports[pair] = result
    return deliver(
        events,
        events_path,
        output,
        best,
        results,
        selected_reports,
        manifests,
        scan_errors,
        horizon,
        lookback,
        parser_sha,
    )


def deliver(
    events,
    events_path,
    output,
    best,
    results,
    selected_reports,
    manifests,
    scan_errors,
    horizon,
    lookback,
    parser_sha,
):
    added = [
        "observation_date",
        "prediction_horizon_months",
        "financial_report_id",
        "financial_missing",
        "financial_missing_reason",
        "report_period_end",
        "filing_month",
        "availability_upper_bound",
        "availability_basis",
        "exact_filing_date",
        "financial_currency",
        "financial_fact_count",
        "financial_conflicting_metrics",
        "report_age_days",
    ]
    metrics = list(ALIASES)
    rows, coverage = [], Counter()
    used = {}
    for event in events:
        observation = month_shift(event["reference_month"], -horizon)
        pair = (event["company_id"], observation)
        result = selected_reports.get(pair)
        if not event["company_id"]:
            reason = "company_number_requires_registry_review"
        elif not best[pair]:
            reason = "not_found_in_scanned_electronic_archive_window"
        elif not result:
            reason = ";".join(sorted({results[document_id(e)]["status"] for e in best[pair]}))
        else:
            reason = ""
        coverage[reason or "matched"] += 1
        facts = result.get("facts", {}) if result else {}
        entry = result["entry"] if result else {}
        if result and (
            entry["company_id"] != event["company_id"]
            or entry["available_by"] > month_end(observation)
            or entry["period_end"] > month_end(observation)
        ):
            raise ValueError("Financial selection violates company or observation-time boundary")
        if result:
            used[result["report_id"]] = result
        monetary_units = {f["unit"] for metric, f in facts.items() if metric != "average_employees"}
        row = {
            **event,
            "observation_date": month_end(observation),
            "prediction_horizon_months": horizon,
            "financial_report_id": result["report_id"] if result else "",
            "financial_missing": not bool(result),
            "financial_missing_reason": reason,
            "report_period_end": entry.get("period_end", ""),
            "filing_month": entry.get("filing_month", ""),
            "availability_upper_bound": entry.get("available_by", ""),
            "availability_basis": "filing_archive_month_plus_one_month_end_conservative_bound"
            if result
            else "",
            "exact_filing_date": "",
            "financial_currency": next(iter(monetary_units), ""),
            "financial_fact_count": len(facts),
            "financial_conflicting_metrics": ";".join(result["conflicting_metrics"])
            if result
            else "",
            "report_age_days": (
                date.fromisoformat(month_end(observation)) - date.fromisoformat(entry["period_end"])
            ).days
            if result
            else "",
        }
        for metric in metrics:
            row[metric] = facts.get(metric, {}).get("value", "")
            row[metric + "_missing"] = metric not in facts
        rows.append(row)
    fields = (
        list(events[0])
        + added
        + [field for metric in metrics for field in (metric, metric + "_missing")]
    )
    write_csv(output / "event-financials.csv", rows, fields)
    report_rows = []
    with gzip.open(output / "financial-facts.jsonl.gz", "wt", encoding="utf-8") as stream:
        for identity, result in sorted(used.items()):
            entry = result["entry"]
            report_rows.append(
                {
                    "report_id": identity,
                    "company_id": entry["company_id"],
                    "period_end": entry["period_end"],
                    "filing_month": entry["filing_month"],
                    "availability_upper_bound": entry["available_by"],
                    "archive_url": entry["url"],
                    "archive_etag": entry["archive"]["etag"],
                    "archive_size": entry["archive"]["archiveSize"],
                    "member": entry["member"],
                    "member_offset": entry["offset"],
                    "member_crc32": entry["crc32"],
                    "member_sha256": result["raw_sha256"],
                    "raw_cache_path": result["raw_cache"],
                    "document_identity_verified": result["identity_verified_in_document"],
                    "conflicting_metrics": ";".join(result["conflicting_metrics"]),
                }
            )
            for fact in result["facts"].values():
                stream.write(
                    json.dumps(
                        {"report_id": identity, "member_sha256": result["raw_sha256"], **fact}
                    )
                    + "\n"
                )
    report_fields = [
        "report_id",
        "company_id",
        "period_end",
        "filing_month",
        "availability_upper_bound",
        "archive_url",
        "archive_etag",
        "archive_size",
        "member",
        "member_offset",
        "member_crc32",
        "member_sha256",
        "raw_cache_path",
        "document_identity_verified",
        "conflicting_metrics",
    ]
    write_csv(output / "financial-reports.csv", report_rows, report_fields)
    write_json(
        output / "retrieval-errors.json",
        [
            {
                "report_id": result["report_id"],
                "member": result["entry"]["member"],
                "status": result["status"],
                "error": result.get("error", ""),
            }
            for result in results.values()
            if result["status"] != "parsed"
        ],
    )
    report = {
        "eventRows": len(events),
        "joinedRows": len(rows),
        "eventsSha256": sha(events_path),
        "horizonMonths": horizon,
        "filingArchiveLookbackMonths": lookback,
        "matchedEventRows": coverage["matched"],
        "missingReasons": dict(coverage),
        "uniqueFinancialReports": len(used),
        "indexesScanned": len(manifests),
        "indexErrors": scan_errors,
        "documentStates": dict(Counter(r["status"] for r in results.values())),
        "metricObservedRows": {
            metric: sum(not row[metric + "_missing"] for row in rows) for metric in metrics
        },
        "parserSha256": parser_sha,
        "pipelineSha256": sha(Path(__file__)),
        "transfer": TRANSFER,
        "exactFilingDatesAvailable": False,
        "conservativeMonthlyAvailabilityAssumption": True,
        "normalControlsAdded": False,
        "modelTrained": False,
    }
    write_json(output / "report.json", report)
    log(json.dumps(report, ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--lookback", type=int, default=36)
    parser.add_argument("--index-workers", type=int, default=3)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    prepare(
        args.events,
        args.output,
        args.cache,
        args.horizon,
        args.lookback,
        args.index_workers,
        args.workers,
    )


if __name__ == "__main__":
    main()
