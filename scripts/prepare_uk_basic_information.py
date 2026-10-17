"""Left-join dated corporate facts and explicitly separate the current register snapshot."""

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from prepare_uk_financials import document_id, month_end, sha, write_csv, write_json
from uk_financials.basic import FIELDS, age_days, parse_basic_document, snapshot_date

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "outputs/uk-controls-2020-2025-h12-1to1-v1"
OUTPUT = ROOT / "outputs/uk-basic-information-20261017-v1"
SNAPSHOT = (
    ROOT / "datasets/sources/companies-house-2026-10-01/BasicCompanyDataAsOneFile-2026-10-01.zip"
)
SNAPSHOT_SHA = "29d54c17e5bf39862a08d5ebf1ae83abc079c8591c8c6d1bab0a29879accb4ee"
SNAPSHOT_FIELDS = (
    "CompanyName",
    "CompanyCategory",
    "CompanyStatus",
    "CountryOfOrigin",
    "IncorporationDate",
    "DissolutionDate",
    "RegAddress.AddressLine1",
    "RegAddress.AddressLine2",
    "RegAddress.PostTown",
    "RegAddress.County",
    "RegAddress.Country",
    "RegAddress.PostCode",
    "SICCode.SicText_1",
    "SICCode.SicText_2",
    "SICCode.SicText_3",
    "SICCode.SicText_4",
    "Accounts.AccountCategory",
    "Accounts.LastMadeUpDate",
    "URI",
)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def snapshot_records(companies, output, source):
    """A cache is reusable only for exactly this company set and frozen source."""
    import io
    from zipfile import ZipFile

    cache = output / "snapshot-raw-records.jsonl.gz"
    target_sha = hashlib.sha256("\n".join(sorted(companies)).encode()).hexdigest()
    meta_path = output / "snapshot-selection.json"
    source_sha = sha(source)
    if source_sha != SNAPSHOT_SHA:
        raise ValueError("Unexpected frozen company snapshot")
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if metadata.get("targetCompaniesSha256") != target_sha:
        matched, scanned = 0, 0
        seen = set()
        with ZipFile(source) as archive, gzip.open(cache, "wt") as destination:
            members = [m for m in archive.namelist() if m.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError("Expected one basic company CSV")
            member = members[0]
            with archive.open(member) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                for number, record in enumerate(reader, 1):
                    scanned += 1
                    row = {key.strip(): value for key, value in record.items()}
                    company = row["CompanyNumber"].strip().upper()
                    if company not in companies:
                        continue
                    if company in seen:
                        raise ValueError("Duplicate snapshot company")
                    seen.add(company)
                    digest = hashlib.sha256(
                        json.dumps(
                            row, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                        ).encode()
                    ).hexdigest()
                    destination.write(
                        json.dumps(
                            {
                                "company_id": company,
                                "member": member,
                                "record_number": number,
                                "row_sha256": digest,
                                "row": row,
                            }
                        )
                        + "\n"
                    )
                    matched += 1
        metadata = {
            "targetCompanies": len(companies),
            "targetCompaniesSha256": target_sha,
            "matchedCompanies": matched,
            "snapshotRowsScanned": scanned,
            "sourceSha256": source_sha,
            "sourceFileDate": "2026-10-01",
            "compiledThrough": "2026-09-30",
        }
        write_json(meta_path, metadata)
    records = {}
    with gzip.open(cache, "rt") as stream:
        for line in stream:
            item = json.loads(line)
            digest = hashlib.sha256(
                json.dumps(
                    item["row"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            if (
                digest != item["row_sha256"]
                or item["company_id"] not in companies
                or item["company_id"] in records
            ):
                raise ValueError("Invalid snapshot evidence cache")
            records[item["company_id"]] = item
    if len(records) != metadata["matchedCompanies"]:
        raise ValueError("Incomplete snapshot cache")
    return records


def extract_report(report):
    raw = gzip.decompress(Path(report["raw_cache_path"]).read_bytes())
    if (
        hashlib.sha256(raw).hexdigest() != report["member_sha256"]
        or len(raw) != int(report["member_size"])
        or zlib.crc32(raw) != int(report["member_crc32"])
    ):
        raise ValueError(f"Source integrity mismatch: {report['report_id']}")
    profile = parse_basic_document(raw, report["company_id"], report["period_end"])
    return {**report, **profile}


def reference(company, snapshots):
    item = snapshots.get(company, {})
    record = item.get("row", {})
    result = {
        "company_id": company,
        "snapshot_missing": not bool(item),
        "snapshot_file_date": "2026-10-01",
        "snapshot_compiled_through": "2026-09-30",
        "snapshot_record_number": item.get("record_number", ""),
        "snapshot_row_sha256": item.get("row_sha256", ""),
    }
    for field in SNAPSHOT_FIELDS:
        value = record.get(field, "")
        if field.endswith("Date") and value:
            value = snapshot_date(value)
        result["snapshot_" + field] = value
    for number in range(1, 5):
        value = record.get(f"SICCode.SicText_{number}", "").strip()
        result[f"snapshot_sic2007_{number}"] = (
            value[:5] if len(value) >= 5 and value[:5].isdigit() else ""
        )
    return result


def historical(profile, observation):
    if profile and (
        profile["availability_upper_bound"] > observation or profile["period_end"] > observation
    ):
        raise ValueError("Future corporate profile selected")
    values = profile["values"] if profile else {}
    result = {
        "historical_basic_report_id": profile["report_id"] if profile else "",
        "historical_basic_period_end": profile["period_end"] if profile else "",
        "historical_basic_available_by_assumed": profile["availability_upper_bound"]
        if profile
        else "",
        "historical_registry_status": "",
        "historical_registry_status_missing": True,
    }
    for field in FIELDS:
        value = values.get(field, "")
        result["historical_" + field] = value
        result["historical_" + field + "_missing"] = value == ""
    age = age_days(observation, values.get("incorporation_date", ""))
    result.update(historical_company_age_days=age, historical_company_age_days_missing=age == "")
    return result


def extra_reports(excluded, reports):
    wanted = {(r["company_id"], r["observation_month"]) for r in excluded}
    mapping = {}
    selection = ROOT / "outputs/uk-financials-2020-2025-h12-v1/selection.jsonl.gz"
    with gzip.open(selection, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            key = row["company_id"], row["observation_month"]
            if key not in wanted or not row["entries"]:
                continue
            entry = row["entries"][0]
            report_id = document_id(entry)
            mapping[key] = report_id
            if report_id in reports:
                continue
            raw_path = (
                ROOT / f"datasets/sources/uk-financials/documents/{report_id[:2]}/{report_id}.gz"
            )
            if not raw_path.exists():
                mapping.pop(key)
                continue
            raw = gzip.decompress(raw_path.read_bytes())
            reports[report_id] = {
                "report_id": report_id,
                "company_id": entry["company_id"],
                "period_end": entry["period_end"],
                "filing_month": entry["filing_month"],
                "availability_upper_bound": entry["available_by"],
                "archive_url": entry["url"],
                "archive_etag": entry["archive"]["etag"],
                "member": entry["member"],
                "member_size": entry["size"],
                "member_crc32": entry["crc32"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_cache_path": str(raw_path),
            }
    return mapping


def run(output, workers):
    output.mkdir(parents=True, exist_ok=True)
    features = list(read_csv(COHORT / "features.csv"))
    excluded = list(read_csv(COHORT / "excluded-cases.csv"))
    companies = {r["company_id"] for r in features + excluded}
    snapshots = snapshot_records(companies, output, SNAPSHOT)
    reports = {r["report_id"]: r for r in read_csv(COHORT / "baseline-reports.csv")}
    excluded_reports = extra_reports(excluded, reports)
    profiles = {}
    parser_sha = sha(Path(__file__).parent / "uk_financials/basic.py")
    cache_dir = output / ".profile-batches"
    cache_dir.mkdir(exist_ok=True)
    ordered = sorted(reports)
    with (
        ProcessPoolExecutor(max_workers=workers) as pool,
        gzip.open(output / "historical-basic-profiles.jsonl.gz", "wt") as evidence,
    ):
        for start in range(0, len(ordered), 1000):
            ids = ordered[start : start + 1000]
            batch_path = cache_dir / f"{start:06d}-{parser_sha[:12]}.jsonl.gz"
            if batch_path.exists():
                with gzip.open(batch_path, "rt") as stream:
                    batch = [json.loads(line) for line in stream]
                if [p["report_id"] for p in batch] != ids:
                    raise ValueError("Wrong cached profile batch")
            else:
                batch = list(pool.map(extract_report, [reports[key] for key in ids], chunksize=25))
                temporary = batch_path.with_suffix(".tmp")
                with gzip.open(temporary, "wt") as stream:
                    for profile in batch:
                        stream.write(json.dumps(profile) + "\n")
                temporary.replace(batch_path)
            for profile in batch:
                evidence.write(json.dumps(profile) + "\n")
                profiles[profile["report_id"]] = {
                    k: profile[k]
                    for k in (
                        "report_id",
                        "company_id",
                        "values",
                        "conflicts",
                        "period_end",
                        "availability_upper_bound",
                    )
                }
            print(
                json.dumps(
                    {"profilesCompleted": min(start + 1000, len(ordered)), "total": len(ordered)}
                ),
                flush=True,
            )
    references = {company: reference(company, snapshots) for company in sorted(companies)}
    write_csv(
        output / "company-reference.csv", references.values(), list(next(iter(references.values())))
    )
    labels = {r["sample_id"]: r for r in read_csv(COHORT / "labels.csv")}
    coverage = {role: Counter() for role in ("case", "control", "excluded_case")}
    original_fields = list(features[0])
    history_fields = list(historical(None, "2000-01-01"))
    basic_fields = (
        ["sample_id", "company_id", "observation_date", "display_name"]
        + history_fields
        + [k for k in next(iter(references.values())) if k != "company_id"]
        + [
            "snapshot_backfilled_age_days_at_observation",
            "snapshot_backfilled_age_days_at_observation_missing",
        ]
    )

    def enrich(row, profile, role):
        observation = row["observation_date"]
        if profile and profile["company_id"] != row["company_id"]:
            raise ValueError("Wrong company association")
        history = historical(profile, observation)
        ref = references[row["company_id"]]
        age = age_days(observation, ref["snapshot_IncorporationDate"])
        counts = coverage[role]
        counts["rows"] += 1
        counts["snapshot_matched"] += not ref["snapshot_missing"]
        counts["historical_report"] += bool(profile)
        for field in FIELDS:
            counts["historical_" + field] += not history["historical_" + field + "_missing"]
        counts["historical_company_age_days"] += not history["historical_company_age_days_missing"]
        counts["snapshot_backfilled_age_days"] += age != ""
        return {
            "sample_id": row.get("sample_id", ""),
            "company_id": row["company_id"],
            "observation_date": observation,
            "display_name": history["historical_registered_name"]
            or row.get("company_name")
            or row["company_id"],
            **history,
            **ref,
            "snapshot_backfilled_age_days_at_observation": age,
            "snapshot_backfilled_age_days_at_observation_missing": age == "",
        }

    with (
        (output / "features.csv").open("w", encoding="utf-8-sig", newline="") as feature_stream,
        (output / "sample-basic-information.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as basic_stream,
    ):
        feature_writer = csv.DictWriter(feature_stream, fieldnames=original_fields + history_fields)
        basic_writer = csv.DictWriter(basic_stream, fieldnames=basic_fields)
        feature_writer.writeheader()
        basic_writer.writeheader()
        for row in features:
            combined = enrich(
                row, profiles.get(row["baseline_report_id"]), labels[row["sample_id"]]["role"]
            )
            basic_writer.writerow(combined)
            feature_writer.writerow({**row, **{field: combined[field] for field in history_fields}})
    excluded_rows = []
    for row in excluded:
        observation = month_end(row["observation_month"])
        combined = enrich(
            {**row, "observation_date": observation},
            profiles.get(excluded_reports.get((row["company_id"], row["observation_month"]))),
            "excluded_case",
        )
        excluded_rows.append({**row, **combined})
    write_csv(output / "excluded-case-basic-information.csv", excluded_rows, list(excluded_rows[0]))
    copied = ("labels.csv", "matches.csv", "excluded-cases.csv")
    for filename in copied:
        shutil.copyfile(COHORT / filename, output / filename)
    contract = json.loads((COHORT / "feature-contract.json").read_text())
    numeric = ["historical_dormant", "historical_company_age_days"]
    categorical = [
        "historical_legal_form",
        "historical_country_of_incorporation",
        "historical_sic2007",
    ]
    for field in numeric + categorical:
        if any(coverage[role][field] for role in ("case", "control")):
            contract[
                "numericFeatureAllowlist" if field in numeric else "categoricalFeatureAllowlist"
            ].append(field)
            contract["numericFeatureAllowlist"].append(field + "_missing")
    contract.update(
        snapshotFieldsAreReferenceOnly=True,
        snapshotMissingnessMustNotBeModelFeature=True,
        historicalDormantIsAccountingPeriodFactNotRegistryStatus=True,
        historicalProfileSelection=(
            "Same baseline report as original cohort; no completeness fallback"
        ),
        availabilityIsConservativeMonthlyAssumptionNotVerifiedPublicationDate=True,
    )
    write_json(output / "feature-contract.json", contract)
    write_json(
        output / "coverage.json",
        {
            "uniqueCompanies": len(companies),
            "snapshotMatchedCompanies": len(snapshots),
            "historicalReports": len(profiles),
            "byRole": coverage,
        },
    )
    write_json(
        output / "source-manifest.json",
        {
            "snapshotSource": str(SNAPSHOT),
            "snapshotSha256": SNAPSHOT_SHA,
            "snapshotUrl": "https://download.companieshouse.gov.uk/en_output.html",
            "cohort": str(COHORT),
            "unchangedFiles": {name: sha(output / name) for name in copied},
            "inputFeaturesSha256": sha(COHORT / "features.csv"),
            "parserSha256": parser_sha,
            "pipelineSha256": sha(Path(__file__)),
            "reusedFinancialSourceBundle": str(COHORT) + "-sources.zip",
        },
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "coverage": {role: dict(counts) for role, counts in coverage.items()},
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    arguments = parser.parse_args()
    run(arguments.output, arguments.workers)
