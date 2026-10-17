"""Historical electronic-filer sampling, independent of companies' current status."""

import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from zipfile import ZipFile

from prepare_uk_adverse_events import company_identity
from prepare_uk_financials import FILENAME, document_id, month_end, month_shift, sha, write_json

from uk_financials.archives import index_archive

PROTOCOL = "historical-electronic-filer-controls-v1"
SEED = "risk-uk-controls-20261017-v1"


def rank(*values):
    return hashlib.blake2b("|".join((SEED, *values)).encode(), digest_size=8).digest()


def registry_group(company):
    if re.fullmatch(r"[0-9]{8}", company):
        return "EW_company"
    return {"SC": "SC_company", "OC": "EW_LLP", "SO": "SC_LLP"}.get(company[:2], "")


def age_band(observation, filing):
    def integer(month):
        year, number = map(int, month.split("-"))
        return year * 12 + number

    age = integer(observation) - integer(filing)
    if not 1 <= age <= 36:
        raise ValueError("Filing falls outside the shared observation window")
    return "01_06" if age <= 6 else "07_12" if age <= 12 else "13_24" if age <= 24 else "25_36"


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def history(archive):
    months = defaultdict(set)
    with ZipFile(archive) as zipped:
        member = next(
            n for n in zipped.namelist() if n.startswith("Record-level") and n.endswith(".csv")
        )
        with io.TextIOWrapper(zipped.open(member), encoding="latin1", newline="") as stream:
            for row in csv.DictReader(stream):
                identity, _ = company_identity(row["company_number"])
                if identity:
                    months[identity].add(row["month_registered"])
    return {company: sorted(values) for company, values in months.items()}


def control_eligible(company, observation, followup_end, event_history):
    if not registry_group(company) or month_shift(observation, 12) != followup_end:
        return False
    if followup_end > "2025-12" or observation < "2019-01":
        return False
    # An event after this horizon must not exclude an otherwise valid earlier control.
    return not any(month <= followup_end for month in event_history.get(company, ()))


def catalog(index_root, cache, denominator=16):
    if denominator < 1:
        raise ValueError("Expected a positive company sampling denominator")
    files = sorted(index_root.glob("*/manifest.json"))
    metadata = {p.parent.name: sha(p) for p in files}
    signature = {
        "protocol": PROTOCOL,
        "seed": SEED,
        "denominator": denominator,
        "indexes": metadata,
    }
    database = cache / "historical-filers.sqlite"
    marker = cache / "catalog-metadata.json"
    if database.exists() and marker.exists() and json.loads(marker.read_text()) == signature:
        return database
    cache.mkdir(parents=True, exist_ok=True)
    if database.exists():
        raise ValueError("Incomplete/different catalog; use a fresh cache directory")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE filings (
            company TEXT, period_end TEXT, filing_month TEXT, member TEXT,
            offset INTEGER, compressed_size INTEGER, size INTEGER, crc INTEGER, compression INTEGER
        )""")
        counts = Counter()
        for manifest_path in files:
            month = manifest_path.parent.name
            frozen = json.loads(manifest_path.read_text())
            _, entries = index_archive(frozen["url"], manifest_path.parent)
            kept = []
            for entry in entries:
                match = FILENAME.search(entry["member"])
                if not match:
                    continue
                company = match[1].upper()
                group = registry_group(company)
                if not group:
                    continue
                if group.endswith("company") and int.from_bytes(rank(company), "big") % denominator:
                    continue
                try:
                    end = date.fromisoformat(f"{match[2][:4]}-{match[2][4:6]}-{match[2][6:]}")
                except ValueError:
                    continue
                kept.append(
                    (
                        company,
                        end.isoformat(),
                        month,
                        entry["member"],
                        entry["offset"],
                        entry["compressedSize"],
                        entry["size"],
                        entry["crc32"],
                        entry["compression"],
                    )
                )
            connection.executemany("INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?)", kept)
            connection.commit()
            counts[month] = len(kept)
            print(f"CATALOG {month} sampled_filings={len(kept)}", flush=True)
        connection.execute(
            "CREATE INDEX filing_company ON filings(company,period_end,filing_month)"
        )
        connection.execute("CREATE INDEX filing_month ON filings(filing_month)")
        connection.commit()
    write_json(cache / "catalog-counts.json", counts)
    write_json(marker, signature)
    return database


def entry_from_row(row, manifests):
    company, end, filing, member, offset, compressed, size, crc, compression = row
    archive = manifests[filing]
    return {
        "company_id": company,
        "period_end": end,
        "filing_month": filing,
        "member": member,
        "offset": offset,
        "compressedSize": compressed,
        "size": size,
        "crc32": crc,
        "compression": compression,
        "url": archive["url"],
        "archive": archive,
        "available_by": month_end(month_shift(filing, 1)),
    }


def latest_pool(connection, observation, manifests):
    cursor = connection.execute(
        """SELECT company,period_end,filing_month,member,offset,
        compressed_size,size,crc,compression FROM (
          SELECT *,ROW_NUMBER() OVER (
            PARTITION BY company ORDER BY period_end DESC,filing_month DESC,member DESC
          ) AS ordinal FROM filings
          WHERE filing_month BETWEEN ? AND ? AND period_end <= ?
        ) WHERE ordinal=1""",
        (
            month_shift(observation, -36),
            month_shift(observation, -1),
            month_end(observation),
        ),
    )
    return (entry_from_row(row, manifests) for row in cursor)


def case_frame(events_path, selection_path, event_history):
    cases, excluded = {}, []
    for row in read_rows(events_path):
        if row["label_candidate"] != "True" or row["is_first_observed_month"] != "True":
            continue
        company = row["company_id"]
        if company in cases:
            cases[company]["evidence_event_ids"].append(row["event_id"])
            continue
        cases[company] = {
            "company_id": company,
            "event_month": row["reference_month"],
            "observation_month": month_shift(row["reference_month"], -12),
            "event_name": row["company_name"],
            "evidence_event_ids": [row["event_id"]],
            "event_review_reasons": row["review_reasons"],
        }
    with gzip.open(selection_path, "rt") as stream:
        for row in map(json.loads, stream):
            case = cases.get(row["company_id"])
            if case and case["observation_month"] == row["observation_month"] and row["entries"]:
                case["entry"] = row["entries"][0]
    eligible = []
    for company, case in sorted(cases.items()):
        reason = (
            "unsupported_registry_prefix"
            if not registry_group(company)
            else "event_observed_at_or_before_baseline"
            if any(m <= case["observation_month"] for m in event_history.get(company, ()))
            else "no_historical_electronic_filing_in_shared_window"
            if "entry" not in case
            else ""
        )
        if reason:
            excluded.append(
                {k: v for k, v in {**case, "exclusion_reason": reason}.items() if k != "entry"}
            )
        else:
            eligible.append(case)
    return eligible, excluded, len(cases)


def sample_pairs(database, cases, manifests, event_history):
    groups = defaultdict(list)
    for case in cases:
        groups[case["observation_month"]].append(case)
    pairs, unmatched, pools = [], [], []
    used_controls = set()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA temp_store=MEMORY")
        for observation, monthly_cases in sorted(groups.items()):
            candidates = defaultdict(list)
            followup = month_shift(observation, 12)
            for entry in latest_pool(connection, observation, manifests):
                company = entry["company_id"]
                if company not in used_controls and control_eligible(
                    company, observation, followup, event_history
                ):
                    key = (registry_group(company), age_band(observation, entry["filing_month"]))
                    candidates[key].append(entry)
            for key, values in candidates.items():
                values.sort(key=lambda e: rank(observation, e["company_id"]), reverse=True)
                pools.append(
                    {
                        "observation_month": observation,
                        "registry_group": key[0],
                        "filing_age_band": key[1],
                        "eligible_sampled_companies": len(values),
                    }
                )
            for case in sorted(monthly_cases, key=lambda c: rank(observation, c["company_id"])):
                key = (
                    registry_group(case["company_id"]),
                    age_band(observation, case["entry"]["filing_month"]),
                )
                if not candidates[key]:
                    unmatched.append(
                        {
                            **case,
                            "exclusion_reason": "no_control_in_exact_month_registry_age_stratum",
                        }
                    )
                    continue
                control = candidates[key].pop()
                used_controls.add(control["company_id"])
                pair_id = hashlib.sha256(
                    (PROTOCOL + case["company_id"] + observation).encode()
                ).hexdigest()
                pairs.append({"pair_id": pair_id, "case": case, "control_entry": control})
            print(
                f"MATCH {observation} cases={len(monthly_cases)} cumulative_pairs={len(pairs)}",
                flush=True,
            )
    return pairs, unmatched, pools


def baseline_report_ids(pairs):
    return {
        document_id(entry): entry
        for pair in pairs
        for entry in (pair["case"]["entry"], pair["control_entry"])
    }
