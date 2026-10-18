"""Collect official registry date evidence without rewriting research labels or features."""

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from run_uk_jevforge import calibration_lines

HOST = "https://find-and-update.company-information.service.gov.uk"
RANK = {"train": 0, "calibration": 1, "valid": 2, "test": 3}
IX = {"http://www.xbrl.org/2013/inlineXBRL", "http://www.xbrl.org/2008/inlineXBRL"}
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def csv_write(path, items):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        if items:
            writer = csv.DictWriter(stream, fieldnames=list(items[0]))
            writer.writeheader()
            writer.writerows(items)


def text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_date(value):
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text(value), fmt).replace(tzinfo=timezone.utc).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Unrecognised registry date: " + value)


def filings(raw, company):
    document = raw.decode("utf-8")
    if f"Company number {company}" not in text(document):
        raise ValueError("Company identity missing from filing history")
    table = re.search(r'<table\b[^>]*id="fhTable"[^>]*>(.*?)</table>', document, re.DOTALL)
    if not table:
        raise ValueError("Filing table missing; do not interpret challenge pages as empty history")
    result = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table[1], re.DOTALL):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 3:
            continue
        urls = re.findall(r'href="([^"]+)"', row)
        links = [urllib.parse.urljoin(HOST, html.unescape(u)) for u in urls]
        result.append({
            "date": parse_date(cells[0]), "type": text(cells[1]),
            "description": text(cells[2]),
            "xhtml": next((u for u in links if "format=xhtml" in u), ""),
            "pdf": next((u for u in links if "format=pdf" in u), ""),
        })
    following = re.search(r'<a\b[^>]*id="next-page"[^>]*href="([^"]+)"', document)
    return result, urllib.parse.urljoin(HOST, html.unescape(following[1])) if following else ""


def insolvencies(raw, company):
    document = raw.decode("utf-8")
    if f"Company number {company}" not in text(document):
        raise ValueError("Company identity missing from insolvency page")
    result = []
    for chunk in re.split(r'(?=<p\b[^>]*id="case-\d+")', document)[1:]:
        heading = re.search(r'<p\b[^>]*id="case-\d+"[^>]*>(.*?)</p>', chunk, re.DOTALL)
        if not heading or "Compulsory liquidation" not in text(heading[1]):
            continue
        item = {}
        for key, value in re.findall(r'<dd\b[^>]*id="([^"]+)_date_\d+"[^>]*>(.*?)</dd>', chunk, re.DOTALL):
            item[key] = parse_date(value)
        result.append(item)
    return result


def ix_fingerprint(raw):
    """Compare tagged facts and complete contexts/units, independent of HTML rendering."""
    namespace_stack, pending, scopes = [], [], {}
    root = None
    for event, value in ET.iterparse(io.BytesIO(raw), events=("start-ns", "start", "end")):
        if event == "start-ns":
            pending.append(value)
        elif event == "start":
            scope = dict(namespace_stack[-1]) if namespace_stack else {}
            scope.update(pending)
            pending.clear()
            namespace_stack.append(scope)
            scopes[id(value)] = scope
            if root is None:
                root = value
        else:
            namespace_stack.pop()
    if root is None:
        raise ValueError("Empty XML")

    def qname(value, node):
        if ":" in value and not value.startswith("{"):
            prefix, name = value.split(":", 1)
            if prefix in scopes[id(node)]:
                return "{" + scopes[id(node)][prefix] + "}" + name
        return value

    def normal(node):
        attributes = sorted((k, qname(v, node) if k in {"name", "format", "dimension"} else v)
                            for k, v in node.attrib.items())
        content = " ".join((node.text or "").split())
        if node.tag in {f"{{{XBRLI}}}measure", f"{{{XBRLDI}}}explicitMember"}:
            content = qname(content, node)
        return [node.tag, attributes, content,
                [[normal(c), " ".join((c.tail or "").split())] for c in node]]

    records = []
    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith("{"):
            continue
        namespace, name = node.tag[1:].split("}", 1)
        if namespace in IX and name in {"nonFraction", "nonNumeric", "fraction", "continuation"}:
            # Presentation tags may be rewritten by the registry renderer; preserve their text.
            attributes = sorted((k, qname(v, node) if k in {"name", "format"} else v)
                                for k, v in node.attrib.items())
            records.append([node.tag, attributes, "".join("".join(node.itertext()).split())])
        elif namespace == XBRLI and name in {"context", "unit"}:
            records.append(normal(node))
    if not any(r[0].endswith("}nonFraction") for r in records):
        raise ValueError("No numeric inline XBRL facts")
    return digest(json.dumps(sorted(records, key=str), ensure_ascii=True).encode()), len(records)


class Fetcher:
    def __init__(self, directory, interval=0.5):
        self.directory, self.interval = directory, interval
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock, self.next_time = threading.Lock(), 0.0

    def get(self, url):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in {
            "find-and-update.company-information.service.gov.uk", "www.gov.uk",
            "download.companieshouse.gov.uk",
        }:
            raise ValueError("Unexpected evidence host")
        key = digest(url.encode())
        target = self.directory / (key + ".gz")
        metadata = self.directory / (key + ".json")
        if target.exists() and metadata.exists():
            content = gzip.decompress(target.read_bytes())
            info = json.loads(metadata.read_text())
            if digest(content) != info["sha256"] or info["url"] != url:
                raise ValueError("Cached source checksum mismatch")
            return content, info
        for attempt in range(3):
            with self.lock:
                delay = max(0, self.next_time - time.monotonic())
                self.next_time = max(self.next_time, time.monotonic()) + self.interval
            if delay:
                time.sleep(delay)
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "UK-Research-Date-Audit/1.0"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    content = response.read(32 * 1024 * 1024 + 1)
                    if len(content) > 32 * 1024 * 1024:
                        raise ValueError("Evidence exceeds bounded download size")
                    info = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": digest(content), "bytes": len(content),
                            "content_type": response.headers.get("Content-Type"),
                            "cache_path": str(target)}
                target.write_bytes(gzip.compress(content))
                write(metadata, info)
                return content, info
            except (urllib.error.URLError, TimeoutError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code in {401, 403, 404}:
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError("Unreachable")


def event_verdict(label, entries, cases):
    # WU01(Scot) is the winding-up order filing; appointments and petitions are not substitutes.
    orders = [r for r in entries if r["type"].lower() == "wu01(scot)"]
    dates = sorted({r["date"] for r in orders})
    target = label["target_event_month"]
    matching = [r for r in orders if r["date"][:7] == target]
    starts = sorted({r["wound-up-on"] for r in cases if r.get("wound-up-on")})
    return {
        "registry_month_status": "order_filing_month_matches" if matching else "unresolved_no_matching_order_filing",
        "target_event_month": target,
        "court_order_filing_dates": ";".join(dates),
        "winding_up_start_dates": ";".join(starts),
        "start_month_differs_from_target": any(d[:7] != target for d in starts),
        "start_on_or_before_observation": any(d[:7] <= label["observation_month"] for d in starts),
        "exact_court_order_date_verified": False,
        "order_document_urls": ";".join(r["pdf"] for r in matching),
    }


def verify_report(report, entries, fetcher):
    candidates = []
    for entry in entries:
        if entry["type"] not in {"AA", "AAMD"}:
            continue
        made_up = re.search(r"made up to (\d{1,2} [A-Za-z]+ \d{4})", entry["description"])
        if made_up and parse_date(made_up[1]) == report["period_end"]:
            candidates.append(entry)
    result = {"report_id": report["report_id"], "company_id": report["company_id"],
              "period_end": report["period_end"], "filing_month": report["filing_month"],
              "availability_upper_bound_assumed": report["availability_upper_bound"],
              "status": "unresolved_no_matching_filing", "candidate_count": len(candidates),
              "filing_date_exact": "", "filing_date_exact_verified": False,
              "archive_month_matches_registry_date": "",
              "exact_publication_timestamp_verified": False, "match_method": "",
              "candidate_filing_dates": ";".join(r["date"] for r in candidates),
              "document_url": "", "evidence_sha256": "", "error": ""}
    if not candidates:
        return result
    local = gzip.decompress(Path(report["raw_cache_path"]).read_bytes())
    if digest(local) != report["member_sha256"]:
        raise ValueError("Original monthly archive member checksum mismatch")
    local_fp = None
    matches = []
    for candidate in candidates:
        if not candidate["xhtml"]:
            continue
        raw, info = fetcher.get(candidate["xhtml"])
        method = "byte_identical"
        if digest(raw) != report["member_sha256"]:
            if local_fp is None:
                local_fp = ix_fingerprint(local)
            if ix_fingerprint(raw) != local_fp:
                continue
            method = "ixbrl_facts_contexts_units_match_ignoring_text_whitespace"
        matches.append((candidate, info, method))
    if len(matches) == 1:
        entry, info, method = matches[0]
        result.update(status="verified_registry_filing_date", filing_date_exact=entry["date"],
                      filing_date_exact_verified=True, match_method=method,
                      archive_month_matches_registry_date=entry["date"][:7] == report["filing_month"],
                      document_url=entry["xhtml"], evidence_sha256=info["sha256"])
    elif len(matches) > 1:
        result["status"] = "unresolved_multiple_identical_filings"
    else:
        result["status"] = "unresolved_document_identity_not_proven"
    return result


def verify_company(task, fetcher):
    company, label, reports = task
    entries, pages, error, cases = [], [], "", []
    url = f"{HOST}/company/{company}/filing-history"
    try:
        visited = set()
        while url and url not in visited:
            visited.add(url)
            raw, info = fetcher.get(url)
            page, url = filings(raw, company)
            pages.append(info)
            entries.extend(page)
            # Read the complete company history to retain ambiguity and earlier procedures.
            if len(visited) >= 100 and url:
                raise ValueError("Filing history exceeded 100 pages")
    except (OSError, ValueError, ET.ParseError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    history_error = error
    insolvency_url = f"{HOST}/company/{company}/insolvency"
    try:
        raw, info = fetcher.get(insolvency_url)
        cases = insolvencies(raw, company)
        pages.append(info)
    except (OSError, ValueError, ET.ParseError) as exc:
        error += f"; insolvency: {type(exc).__name__}: {exc}"
    event = {"sample_id": label["sample_id"], "company_id": company,
             "partition": label["partition"], "observation_month": label["observation_month"],
             **event_verdict(label, entries, cases), "history_complete": not error,
             "error": error, "history_url": f"{HOST}/company/{company}/filing-history",
             "insolvency_url": insolvency_url,
             "source_page_sha256": ";".join(p["sha256"] for p in pages)}
    if error:
        event["registry_month_status"] = "unresolved_fetch_or_parse_error"
    verified = []
    for report in reports:
        try:
            item = verify_report(report, entries, fetcher)
        except (OSError, ValueError, ET.ParseError) as exc:
            item = {"report_id": report["report_id"], "company_id": company,
                    "status": "unresolved_fetch_or_parse_error", "error": f"{type(exc).__name__}: {exc}"}
        if history_error:
            item.update(status="unresolved_history_incomplete", filing_date_exact_verified=False,
                        filing_date_exact="", error=history_error)
        verified.append(item)
    return {"event": event, "reports": verified, "pages": pages}


def prepare(source, decisions, audit, output):
    output.mkdir(parents=True, exist_ok=False)
    index = [json.loads(line) for line in (decisions / "sample-index.jsonl").open()]
    calibration = calibration_lines([r for r in index if r["split"] == "train"])
    partitions = {r["sample_id"]: ("calibration" if r["line"] in calibration else "train")
                  if r["split"] == "train" else r["split"] for r in index}
    review_ids = {r["sample_id"] for r in rows(audit / "issues.csv")
                  if r["code"] == "event_source_review" and "scottish_compulsory" in r["detail"]}
    labels = [{**r, "partition": partitions[r["sample_id"]]} for r in rows(source / "labels.csv")
              if r["sample_id"] in review_ids]
    labels.sort(key=lambda r: (RANK[r["partition"]], r["sample_id"]))
    csv_write(output / "event-queue.csv", labels)
    report_partitions = {}
    for link in rows(source / "sample-history-links.csv"):
        partition = partitions.get(link["sample_id"])
        if partition is not None:
            key = link["report_id"]
            previous = report_partitions.get(key)
            if previous is None or RANK[partition] < RANK[previous]:
                report_partitions[key] = partition
    companies = {r["company_id"] for r in labels}
    reports = [{**r, "priority_partition": report_partitions.get(r["report_id"], "unused"),
                "in_event_company_batch": r["company_id"] in companies}
               for r in rows(source / "financial-report-sources.csv")]
    reports.sort(key=lambda r: (RANK.get(r["priority_partition"], 4), r["company_id"], r["report_id"]))
    csv_write(output / "financial-queue.csv", reports)
    write(output / "inputs.json", {"scope": "All 1077 Scottish review samples and their source reports; full financial backlog inventoried separately",
          "event_samples": len(labels), "event_partitions": dict(Counter(r["partition"] for r in labels)),
          "financial_sources": len(reports), "financial_priority_counts": dict(Counter(r["priority_partition"] for r in reports)),
          "event_company_reports": sum(r["in_event_company_batch"] for r in reports),
          "source_sha256": {str(p): digest(p.read_bytes()) for p in [source / "labels.csv", source / "financial-report-sources.csv", source / "sample-history-links.csv", decisions / "sample-index.jsonl", audit / "issues.csv"]}})


def collect(output, workers):
    fetcher = Fetcher(output / "official-pages")
    labels = list(rows(output / "event-queue.csv"))
    reports = {}
    for report in rows(output / "financial-queue.csv"):
        if report["in_event_company_batch"] == "True":
            reports.setdefault(report["company_id"], []).append(report)
    done_dir = output / "companies"
    done_dir.mkdir(exist_ok=True)
    tasks = [(r["company_id"], r, reports.get(r["company_id"], [])) for r in labels
             if not (done_dir / (r["company_id"] + ".json")).exists()]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(lambda t: verify_company(t, fetcher), tasks):
            write(done_dir / (result["event"]["company_id"] + ".json"), result)
            done = len(list(done_dir.glob("*.json")))
            if done % 10 == 0:
                write(output / "status.json", {"stage": "collecting", "companies_done": done, "companies_total": len(labels)})
                print(f"Verified company sources {done}/{len(labels)}", flush=True)
    summarize(output)


def verify_financial_company(task, fetcher):
    company, reports = task
    entries, pages, error = [], [], ""
    url = f"{HOST}/company/{company}/filing-history"
    oldest = min(r["period_end"][:7] for r in reports)
    try:
        visited = set()
        while url and url not in visited:
            visited.add(url)
            raw, info = fetcher.get(url)
            page, url = filings(raw, company)
            pages.append(info)
            entries.extend(page)
            dates = [r["date"] for r in page]
            # Search earlier filings too: bulk archive month is not proof of filing month.
            if dates == sorted(dates, reverse=True) and dates and dates[-1][:7] < oldest:
                break
            if len(visited) >= 100 and url:
                raise ValueError("Filing history exceeded 100 pages")
    except (OSError, ValueError, ET.ParseError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    results = []
    for report in reports:
        try:
            result = verify_report(report, entries, fetcher)
        except (OSError, ValueError, ET.ParseError) as exc:
            result = {"report_id": report["report_id"], "company_id": company,
                      "status": "unresolved_fetch_or_parse_error", "error": f"{type(exc).__name__}: {exc}"}
        if error:
            result.update(status="unresolved_history_incomplete", filing_date_exact_verified=False,
                          filing_date_exact="", error=error)
        results.append(result)
    return {"company_id": company, "reports": results, "pages": pages, "history_error": error}


def collect_financial(output, workers, partition):
    fetcher = Fetcher(output / "official-pages")
    completed = {}
    for path in (output / "companies").glob("*.json"):
        for report in json.loads(path.read_text())["reports"]:
            completed[report["report_id"]] = report
    done_dir = output / ("financial-" + partition)
    done_dir.mkdir(exist_ok=True)
    for path in done_dir.glob("*.json"):
        for report in json.loads(path.read_text())["reports"]:
            completed[report["report_id"]] = report
    companies = {}
    queued = []
    for report in rows(output / "financial-queue.csv"):
        if report["priority_partition"] != partition:
            continue
        queued.append(report["report_id"])
        if report["report_id"] not in completed:
            companies.setdefault(report["company_id"], []).append(report)
    total = len(queued)
    count = sum(r in completed for r in queued)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(lambda t: verify_financial_company(t, fetcher), companies.items()):
            write(done_dir / (result["company_id"] + ".json"), result)
            for report in result["reports"]:
                completed[report["report_id"]] = report
            count += len(result["reports"])
            if count % 20 == 0 or count == total:
                status = {"stage": "collecting_financial", "partition": partition,
                          "reports_attempted": count, "reports_total": total,
                          "status_counts": dict(Counter(completed[r]["status"] for r in queued if r in completed))}
                write(output / ("financial-" + partition + "-status.json"), status)
                print(json.dumps(status), flush=True)
    keys = sorted({k for r in queued if r in completed for k in completed[r]})
    csv_write(output / ("financial-" + partition + "-verification.csv"),
              [{k: completed[r].get(k, "") for k in keys} for r in queued if r in completed])
    write(output / ("financial-" + partition + "-status.json"),
          {"stage": "batch_complete", "reports_attempted": total, "reports_total": total,
           "status_counts": dict(Counter(completed[r]["status"] for r in queued))})


def summarize(output):
    events, reports = [], []
    for path in sorted((output / "companies").glob("*.json")):
        result = json.loads(path.read_text())
        events.append(result["event"])
        reports.extend(result["reports"])
    events.sort(key=lambda r: (RANK[r["partition"]], r["sample_id"]))
    csv_write(output / "event-verification.csv", events)
    if reports:
        keys = sorted({k for r in reports for k in r})
        csv_write(output / "financial-verification.csv", [{k: r.get(k, "") for k in keys} for r in reports])
    merged_reports = {r["report_id"]: r for r in reports}
    for partition in RANK:
        for path in (output / ("financial-" + partition)).glob("*.json"):
            for report in json.loads(path.read_text())["reports"]:
                merged_reports[report["report_id"]] = report
    all_reports = list(merged_reports.values())
    inputs = json.loads((output / "inputs.json").read_text())
    summary = {"companies_collected": len(events), "companies_planned": inputs["event_samples"],
               "event_status": dict(Counter(r["registry_month_status"] for r in events)),
               "by_partition": {p: dict(Counter(r["registry_month_status"] for r in events if r["partition"] == p)) for p in RANK},
               "winding_up_start_month_differs": sum(r["start_month_differs_from_target"] for r in events),
               "winding_up_on_or_before_observation": sum(r["start_on_or_before_observation"] for r in events),
               "financial_status": dict(Counter(r["status"] for r in all_reports)),
               "financial_reports_attempted": len(all_reports),
               "financial_sources_total": inputs["financial_sources"],
               "financial_reports_not_attempted": inputs["financial_sources"] - len(all_reports),
               "verified_archive_month_mismatches": sum(
                   r.get("archive_month_matches_registry_date") is False for r in all_reports),
               "exact_publication_timestamps_verified": 0,
               "research_data_modified": False, "model_retrained": False,
               "script_sha256": digest(Path(__file__).read_bytes())}
    write(output / "summary.json", summary)
    write(output / "status.json", {"stage": "batch_complete" if len(events) == inputs["event_samples"] else "incomplete", **summary})
    print(json.dumps(summary), flush=True)


def pipeline(output, workers):
    job = {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(),
           "script_sha256": digest(Path(__file__).read_bytes()),
           "sequence": ["1077 event reviews and company reports", "train", "calibration", "valid", "test"],
           "max_request_starts_per_second": 2, "stage": "running"}
    write(output / "job.json", job)
    fetcher = Fetcher(output / "official-pages")
    policies = []
    for url in [
        "https://www.gov.uk/government/statistics/company-insolvencies-december-2025/commentary-company-insolvency-statistics-december-2025",
        "https://www.gov.uk/government/statistics/company-insolvencies-december-2025/methodology-and-quality-document-company-insolvency-statistics-december-2025",
        "https://download.companieshouse.gov.uk/en_monthlyaccountsdata.html",
    ]:
        try:
            _, info = fetcher.get(url)
            policies.append(info)
        except (OSError, ValueError) as exc:
            policies.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    write(output / "official-methodology.json", policies)
    collect(output, workers)
    for partition in RANK:
        collect_financial(output, workers, partition)
        summarize(output)
    job.update(stage="collection_complete", finished_at=datetime.now(timezone.utc).isoformat())
    write(output / "job.json", job)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "collect", "financial", "summarize", "pipeline"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("datasets/uk_research"))
    parser.add_argument("--decisions", type=Path, default=Path("datasets/uk_decisions_20261018"))
    parser.add_argument("--audit", type=Path, default=Path("datasets/uk_jev_data_audit_20261018_final"))
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--partition", choices=list(RANK), default="train")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.source, args.decisions, args.audit, args.output)
    elif args.mode == "collect":
        collect(args.output, args.workers)
    elif args.mode == "financial":
        collect_financial(args.output, args.workers, args.partition)
    elif args.mode == "pipeline":
        pipeline(args.output, args.workers)
    else:
        summarize(args.output)


if __name__ == "__main__":
    main()
