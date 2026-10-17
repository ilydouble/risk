"""Build month-matched research controls from historical electronic company accounts."""

import argparse
import gzip
import hashlib
import io
import json
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from prepare_uk_financials import (
    document_id,
    fetch_facts,
    month_end,
    month_shift,
    sha,
    write_csv,
    write_json,
)
from uk_financials.controls import (
    PROTOCOL,
    SEED,
    age_band,
    baseline_report_ids,
    case_frame,
    catalog,
    history,
    registry_group,
    sample_pairs,
)
from uk_financials.facts import ALIASES

REPORT_FIELDS = [
    "report_id",
    "company_id",
    "period_end",
    "filing_month",
    "availability_upper_bound",
    "archive_url",
    "archive_etag",
    "member",
    "member_offset",
    "member_size",
    "member_crc32",
    "member_sha256",
    "raw_cache_path",
    "status",
    "error",
    "document_identity_verified",
    "historical_name",
    "historical_name_missing",
    "conflicting_metrics",
]


def local(tag):
    return str(tag).rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def historical_name(raw_path, period_end):
    raw = gzip.decompress(Path(raw_path).read_bytes())
    if raw.startswith(b"PK\x03\x04"):
        with ZipFile(io.BytesIO(raw)) as zipped:
            members = [
                m
                for m in zipped.infolist()
                if m.filename.lower().endswith((".html", ".xhtml", ".xml"))
            ]
            if len(members) != 1 or members[0].file_size > 50 * 1024 * 1024:
                return ""
            raw = zipped.read(members[0])
    if b"<!ENTITY" in raw.upper():
        return ""
    root = etree.fromstring(
        raw, etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
    )
    if root is None:
        return ""
    contexts = {}
    for node in root.iter():
        if local(node.tag) == "context":
            ends = [
                "".join(x.itertext()).strip()
                for x in node.iter()
                if local(x.tag) in ("instant", "endDate")
            ]
            contexts[node.get("id")] = period_end in ends
    names = set()
    for node in root.iter():
        if local(node.get("name", node.tag)) in (
            "EntityCurrentLegalOrRegisteredName",
            "EntityName",
            "CompanyName",
        ) and contexts.get(node.get("contextRef")):
            value = " ".join("".join(node.itertext()).split())
            if value:
                names.add(value)
    return next(iter(names)) if len(names) == 1 else ""


def retrieve(entry, financial_cache, parser_sha):
    result = fetch_facts(entry, financial_cache, parser_sha)
    name = ""
    if result["status"] in ("parsed", "no_supported_monetary_facts"):
        try:
            name = historical_name(result["raw_cache"], entry["period_end"])
        except (ValueError, etree.XMLSyntaxError, OSError):
            name = ""
    return result, name


def collect(entries, financial_cache, output, workers):
    import csv

    parser_sha = sha(Path(__file__).parent / "uk_financials/facts.py")
    compact, statuses = {}, Counter()
    report_path = output / "baseline-reports.csv"
    with (
        report_path.open("w", encoding="utf-8-sig", newline="") as report_stream,
        gzip.open(output / "baseline-facts.jsonl.gz", "wt") as fact_stream,
        ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        writer = csv.DictWriter(report_stream, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        values = sorted(entries.items())
        futures = {
            pool.submit(retrieve, e, financial_cache, parser_sha): key
            for key, e in values[: workers * 8]
        }
        remaining = iter(values[workers * 8 :])
        while futures:
            completed, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed:
                key = futures.pop(future)
                result, name = future.result()
                entry = entries[key]
                facts = result.get("facts", {})
                statuses[result["status"]] += 1
                row = {
                    "report_id": key,
                    "company_id": entry["company_id"],
                    "period_end": entry["period_end"],
                    "filing_month": entry["filing_month"],
                    "availability_upper_bound": entry["available_by"],
                    "archive_url": entry["url"],
                    "archive_etag": entry["archive"]["etag"],
                    "member": entry["member"],
                    "member_offset": entry["offset"],
                    "member_size": entry["size"],
                    "member_crc32": entry["crc32"],
                    "member_sha256": result.get("raw_sha256", ""),
                    "raw_cache_path": str(Path(result["raw_cache"]).resolve())
                    if result.get("raw_cache")
                    else "",
                    "status": result["status"],
                    "error": result.get("error", ""),
                    "document_identity_verified": result.get(
                        "identity_verified_in_document", False
                    ),
                    "historical_name": name,
                    "historical_name_missing": not bool(name),
                    "conflicting_metrics": ";".join(result.get("conflicting_metrics", [])),
                }
                writer.writerow(row)
                for fact in facts.values():
                    fact_stream.write(json.dumps({"report_id": key, **fact}) + "\n")
                units = {v["unit"] for k, v in facts.items() if k != "average_employees"}
                compact[key] = {
                    "name": name,
                    "status": result["status"],
                    "currency": next(iter(units), ""),
                    "values": {k: v["value"] for k, v in facts.items()},
                }
                following = next(remaining, None)
                if following is not None:
                    next_key, entry = following
                    futures[pool.submit(retrieve, entry, financial_cache, parser_sha)] = next_key
                if len(compact) % 2000 == 0 or len(compact) == len(values):
                    write_json(
                        output / "progress.json",
                        {
                            "stage": "financials",
                            "done": len(compact),
                            "expected": len(values),
                            "states": statuses,
                        },
                    )
                    print(f"FINANCIALS {len(compact)}/{len(values)} {dict(statuses)}", flush=True)
    return compact, statuses, parser_sha


def flatten_excluded(cases):
    return [
        {
            "company_id": c["company_id"],
            "observation_month": c["observation_month"],
            "event_month": c["event_month"],
            "exclusion_reason": c["exclusion_reason"],
            "evidence_event_ids": ";".join(c["evidence_event_ids"]),
        }
        for c in cases
    ]


def prepare(events, event_archive, case_financials, financial_cache, cache, output, workers=48):
    output.mkdir(parents=True, exist_ok=True)
    source_metadata = json.loads((case_financials / "selection-metadata.json").read_text())
    if source_metadata["eventsSha256"] != sha(events):
        raise ValueError("Financial evidence was selected for different event input")
    event_history = history(event_archive)
    manifests = json.loads((case_financials / "archive-manifests.json").read_text())
    selection = case_financials / "selection.jsonl.gz"
    signature = {
        "protocol": PROTOCOL,
        "seed": SEED,
        "ratio": 1,
        "eventsSha256": sha(events),
        "eventArchiveSha256": sha(event_archive),
        "caseSelectionSha256": sha(selection),
        "denominator": 16,
    }
    pairs_path, marker = output / "matched-pairs.jsonl.gz", output / "sampling-metadata.json"
    if marker.exists() and pairs_path.exists():
        metadata = json.loads(marker.read_text())
        if metadata != {**signature, "pairsSha256": sha(pairs_path)}:
            raise ValueError("Sampling inputs changed; use a new output directory")
        with gzip.open(pairs_path, "rt") as stream:
            pairs = list(map(json.loads, stream))
        selection_report = json.loads((output / "sampling-report.json").read_text())
    else:
        database = catalog(financial_cache / "indexes", cache)
        cases, excluded, source_case_count = case_frame(events, selection, event_history)
        pairs, unmatched, pools = sample_pairs(database, cases, manifests, event_history)
        excluded.extend(unmatched)
        with gzip.open(pairs_path, "wt") as stream:
            for pair in pairs:
                stream.write(json.dumps(pair) + "\n")
        write_csv(
            output / "excluded-cases.csv",
            flatten_excluded(excluded),
            [
                "company_id",
                "observation_month",
                "event_month",
                "exclusion_reason",
                "evidence_event_ids",
            ],
        )
        write_csv(
            output / "sampled-pool-counts.csv",
            pools,
            [
                "observation_month",
                "registry_group",
                "filing_age_band",
                "eligible_sampled_companies",
            ],
        )
        selection_report = {
            "sourceFirstObservedCaseCompanies": source_case_count,
            "pairedCases": len(pairs),
            "excludedCases": len(excluded),
            "exclusionReasons": dict(Counter(c["exclusion_reason"] for c in excluded)),
        }
        write_json(output / "sampling-report.json", selection_report)
        write_json(marker, {**signature, "pairsSha256": sha(pairs_path)})
    write_json(output / "archive-manifests.json", manifests)
    entries = baseline_report_ids(pairs)
    compact, statuses, parser_sha = collect(entries, financial_cache, output, workers)
    features, labels, matches = [], [], []
    matched_coverage = Counter()
    for pair in pairs:
        case = pair["case"]
        observation = case["observation_month"]
        ids = {}
        for role, entry in (("case", case["entry"]), ("control", pair["control_entry"])):
            report_id = document_id(entry)
            result = compact[report_id]
            identity = hashlib.sha256((pair["pair_id"] + role).encode()).hexdigest()
            ids[role] = identity
            observed = result["values"]
            row = {
                "sample_id": identity,
                "company_id": entry["company_id"],
                "company_name": result["name"] or entry["company_id"],
                "company_name_missing": not bool(result["name"]),
                "observation_date": month_end(observation),
                "baseline_report_id": report_id,
                "financial_missing": result["status"] != "parsed",
                "financial_missing_reason": ""
                if result["status"] == "parsed"
                else result["status"],
                "financial_currency": result["currency"],
                "report_age_days": (
                    date.fromisoformat(month_end(observation))
                    - date.fromisoformat(entry["period_end"])
                ).days,
            }
            for metric in ALIASES:
                row[metric] = observed.get(metric, "")
                row[metric + "_missing"] = metric not in observed
                matched_coverage[role + ":" + metric] += metric in observed
            features.append(row)
            if result["status"] == "parsed":
                matched_coverage[role + ":financial"] += 1
            labels.append(
                {
                    "sample_id": identity,
                    "pair_id": pair["pair_id"],
                    "company_id": entry["company_id"],
                    "company_group_id": entry["company_id"],
                    "role": role,
                    "label": int(role == "case"),
                    "observation_month": observation,
                    "followup_start_month": month_shift(observation, 1),
                    "followup_end_month": case["event_month"],
                    "prediction_horizon_months": 12,
                    "target_event_month": case["event_month"] if role == "case" else "",
                    "label_meaning": "first_observed_primary_formal_insolvency"
                    if role == "case"
                    else "no_event_observed_in_official_source_through_horizon",
                    "event_evidence_ids": ";".join(case["evidence_event_ids"])
                    if role == "case"
                    else "",
                    "case_event_review_reasons": case["event_review_reasons"]
                    if role == "case"
                    else "",
                    "event_history_start": "2015-01",
                    "event_source_coverage_end": "2025-12",
                    "historical_register_status_verified": False,
                    "all_adverse_states_verified": False,
                }
            )
        matches.append(
            {
                "pair_id": pair["pair_id"],
                "case_sample_id": ids["case"],
                "control_sample_id": ids["control"],
                "observation_month": observation,
                "registry_group": registry_group(case["company_id"]),
                "filing_age_band": age_band(observation, case["entry"]["filing_month"]),
                "industry_matching_verified": False,
                "size_matching_performed": False,
            }
        )
    write_csv(output / "features.csv", features, list(features[0]))
    write_csv(output / "labels.csv", labels, list(labels[0]))
    write_csv(output / "matches.csv", matches, list(matches[0]))
    numeric = ["financial_missing", "report_age_days"] + [
        v for m in ALIASES for v in (m, m + "_missing")
    ]
    write_json(
        output / "feature-contract.json",
        {
            "numericFeatureAllowlist": numeric,
            "categoricalFeatureAllowlist": ["financial_currency"],
            "identifiersAndAuditFieldsAreNotModelFeatures": True,
            "labelsCsvMustNotBeEncodedAsFeatures": True,
            "companyGroupedSplitRequired": True,
            "temporalAndHorizonEmbargoRequired": True,
            "samplePrevalenceIsNotPopulationRisk": True,
            "historicalRegisterStatusFullyVerified": False,
        },
    )
    source_hashes = {
        p.name: sha(p)
        for p in (
            Path(__file__),
            Path(__file__).parent / "uk_financials/controls.py",
            Path(__file__).parent / "uk_financials/archives.py",
        )
    }
    report = {
        **selection_report,
        "controlRows": len(pairs),
        "combinedRows": len(features),
        "uniqueControlCompanies": len({p["control_entry"]["company_id"] for p in pairs}),
        "distinctBaselineReports": len(entries),
        "documentStates": dict(statuses),
        "observedCounts": dict(matched_coverage),
        "parserSha256": parser_sha,
        "sourceCodeSha256": source_hashes,
        "sampling": signature,
        "historicalRegisterStatusVerified": False,
        "currentRegisterUsedForEligibility": False,
        "normalityMeansOnlyNoRecordedFormalEvent": True,
        "industryMatchingPerformed": False,
        "sizeMatchingPerformed": False,
        "monthlyAvailabilityIsAssumed": True,
        "modelTrained": False,
        "workbenchTrainingPackageProduced": False,
    }
    write_json(output / "report.json", report)
    write_json(
        output / "progress.json",
        {"stage": "complete", "pairedCases": len(pairs), "controlRows": len(pairs)},
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--event-archive", required=True, type=Path)
    parser.add_argument("--case-financials", required=True, type=Path)
    parser.add_argument("--financial-cache", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=48)
    args = parser.parse_args()
    prepare(
        args.events,
        args.event_archive,
        args.case_financials,
        args.financial_cache,
        args.cache,
        args.output,
        args.workers,
    )
