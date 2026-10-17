"""Enrich a frozen UK research dataset from an explicit official name snapshot."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

SPLITS = ("train", "valid", "test")
RELATIONS = {
    "SAME_ADDRESS": ("shared_registered_address", "Companies House (legacy)"),
    "EQUITY": ("accounting_parent_type_unspecified", "GLEIF (legacy)"),
    "PREVNAME": ("previous_name_association", "Companies House (legacy)"),
    "SAME_NAME": ("same_name_association", "Companies House (legacy)"),
}
LIMITATIONS = [
    "Labels classify recorded distress status; they are not forward default probabilities.",
    "Names are enriched from a separately dated official snapshot; training inputs are unchanged.",
    "SAME_ADDRESS means a shared registered address, not common ownership or control.",
    "EQUITY is a legacy code. Direct/ultimate parent types and validity dates were lost; "
    "these historical relations have not been reverified against original GLEIF records.",
    "Weights are legacy model weights, not shareholdings or calibrated existence probabilities.",
    "Original age_months uses 2025-12-31; other source dates are not fully recoverable.",
    "Director features use upstream name matching; identity errors cannot be repaired here.",
    "Original address-group splits and pre-split network features are preserved; "
    "this delivery does not certify leakage-free or representative evaluation.",
    "LEI anchors and their address neighbours are a selected subset, not all UK companies.",
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def fingerprint(document):
    # Names and evidence annotations must never change the frozen training graph.
    value = {
        "schema": {
            k: document[k]
            for k in ("feature_names", "relation_names", "hyperedge_types", "target_description")
        },
        "nodes": [
            {k: n[k] for k in ("id", "kind", "community", "features", "label", "split")}
            for n in document["nodes"]
        ],
        "edges": [
            {k: e[k] for k in ("source", "target", "relation", "weight")} for e in document["edges"]
        ],
        "hyperedges": [{k: h[k] for k in ("kind", "members")} for h in document["hyperedges"]],
        "events": document["events"],
    }
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def names_from_archive(archive, wanted):
    matches = {}
    scanned = 0
    with ZipFile(archive) as zipped:
        members = [p for p in zipped.namelist() if p.lower().endswith(".csv")]
        if not members:
            raise ValueError("Official archive contains no CSV")
        for member in members:
            with (
                zipped.open(member) as binary,
                io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream,
            ):
                rows = csv.DictReader(stream)
                rows.fieldnames = [f.strip() for f in rows.fieldnames or []]
                if not {"CompanyName", "CompanyNumber", "CompanyStatus"} <= set(rows.fieldnames):
                    raise ValueError("Missing official company name/number/status columns")
                for record_number, row in enumerate(rows, start=2):
                    scanned += 1
                    identity = row["CompanyNumber"].strip()
                    if identity not in wanted:
                        continue
                    name = row["CompanyName"].strip()
                    if not name:
                        continue
                    if identity in matches:
                        raise ValueError(f"Ambiguous official company identity: {identity}")
                    matches[identity] = {
                        "name": name,
                        "member": member,
                        "recordNumber": record_number,
                        "status": row["CompanyStatus"].strip(),
                    }
    return matches, scanned


def redeliver(source, names_zip, output, version, names_date, names_url):
    if output.exists():
        raise ValueError("Output already exists; choose a new delivery directory")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Output must be outside the frozen source directory")
    audit = json.loads((source / "audit.json").read_bytes())
    metadata = json.loads((source / "export_meta.json").read_bytes())
    wanted = set()
    original = {}
    for split in SPLITS:
        path = source / f"{split}.json"
        sha = digest(path)
        if any(meta["snapshots"][split]["sha256"] != sha for meta in (audit, metadata)):
            raise ValueError(f"Frozen source digest mismatch: {split}")
        document = json.loads(path.read_bytes())
        ids = [n["id"] for n in document["nodes"]]
        if any(not isinstance(identity, str) for identity in ids):
            raise ValueError("Company identities must be strings")
        if len(set(ids)) != len(ids) or wanted.intersection(ids):
            raise ValueError("Repeated company identity or overlapping splits")
        wanted.update(ids)
        original[split] = {"sha256": sha, "trainingFingerprint": fingerprint(document)}
    matches, scanned = names_from_archive(names_zip, wanted)
    if not matches:
        raise ValueError("No official names matched; refusing to publish an empty enrichment")
    names_sha = digest(names_zip)
    data = output / "data"
    data.mkdir(parents=True)
    frozen = data / "legacy-audit"
    frozen.mkdir()
    for filename in ("audit.json", "export_meta.json"):
        (frozen / filename).write_bytes((source / filename).read_bytes())
    stats = {}
    relation_counts = Counter()
    with (
        (output / "enterprises.csv").open("w", encoding="utf-8-sig", newline="") as company_file,
        (data / "name-evidence.csv").open("w", encoding="utf-8-sig", newline="") as evidence_file,
        (output / "unmatched-companies.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as missing_file,
    ):
        companies, evidence, missing = map(csv.writer, (company_file, evidence_file, missing_file))
        feature_names = json.loads((source / "train.json").read_bytes())["feature_names"]
        companies.writerow(
            [
                "company_id",
                "name",
                "snapshot",
                "legacy_label",
                "community",
                *feature_names,
                "name_source_status",
                "name_source_date",
            ]
        )
        evidence.writerow(
            [
                "company_id",
                "name",
                "source_member",
                "source_record_number",
                "source_status",
                "source_date",
            ]
        )
        missing.writerow(["company_id", "snapshot"])
        for split in SPLITS:
            document = json.loads((source / f"{split}.json").read_bytes())
            named = 0
            for node in document["nodes"]:
                match = matches.get(node["id"])
                node["name"] = match["name"] if match else None
                if match:
                    named += 1
                    node.setdefault("properties", {})["nameSource"] = {
                        "url": names_url,
                        "sha256": names_sha,
                        "snapshotDate": names_date,
                        "member": match["member"],
                        "recordNumber": match["recordNumber"],
                        "companyStatusAtNameSnapshot": match["status"],
                    }
                    evidence.writerow(
                        [
                            node["id"],
                            match["name"],
                            match["member"],
                            match["recordNumber"],
                            match["status"],
                            names_date,
                        ]
                    )
                else:
                    missing.writerow([node["id"], split])
                companies.writerow(
                    [
                        node["id"],
                        node["name"],
                        split,
                        node["label"],
                        node["community"],
                        *node["features"],
                        match["status"] if match else "",
                        names_date if match else "",
                    ]
                )
            for index, edge in enumerate(document["edges"]):
                semantic, system = RELATIONS[edge["relation"]]
                edge.update(
                    relation_id=f"{split}:edges:{index}",
                    relation_kind=semantic,
                    source_system=system,
                )
                relation_counts[edge["relation"]] += 1
            for group in document["hyperedges"]:
                director = group["kind"] == "director_group"
                group["semantic_kind"] = "relational" if director else "attribute"
                group["source_system"] = (
                    "legacy_director_name_matching" if director else "Companies House (legacy)"
                )
            if fingerprint(document) != original[split]["trainingFingerprint"]:
                raise ValueError("Training inputs changed during enrichment")
            path = data / f"{split}.json"
            path.write_text(
                json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            )
            labels = Counter(n["label"] for n in document["nodes"])
            stats[split] = {
                "companies": len(document["nodes"]),
                "edges": len(document["edges"]),
                "hyperedges": len(document["hyperedges"]),
                "namesMatched": named,
                "labels": {str(key): value for key, value in labels.items()},
                "sha256": digest(path),
                "size_mb": round(path.stat().st_size / 1048576, 1),
            }
    provenance = {
        "version": version,
        "sourceSnapshots": original,
        "nameSource": {
            "url": names_url,
            "sha256": names_sha,
            "snapshotDate": names_date,
            "license": "Open Government Licence v3",
            "rowsScanned": scanned,
        },
        "companies": len(wanted),
        "namesMatched": len(matches),
        "namesMissing": len(wanted) - len(matches),
        "relationCounts": dict(relation_counts),
        "trainingInputsUnchanged": True,
        "limitations": LIMITATIONS,
        "pipeline": "scripts/redeliver_uk_dataset.py",
        "pipelineSha256": digest(Path(__file__)),
    }
    generated_at = datetime.now(UTC).isoformat()
    audit.update(
        version=version,
        built_at=generated_at,
        snapshots=stats,
        delivery=provenance,
        limitations=LIMITATIONS,
        design="Frozen LEI-anchor/address-neighbour research graph with official name enrichment.",
        edge_weight_policy="Legacy model weights only; see delivery limitations and relation_kind.",
        feature_notes="Frozen legacy raw features. No recomputation or new model result claimed.",
        hyperedge_note="Attribute and upstream name-matched director groups; no new inference.",
    )
    metadata.update(
        version=version, generated_at=generated_at, snapshots=stats, delivery=provenance
    )
    write_json(data / "audit.json", audit)
    write_json(data / "export_meta.json", metadata)
    write_json(data / "delivery-provenance.json", provenance)
    write_json(output / "delivery-report.json", provenance)
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--names-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--names-date", required=True, help="Source snapshot as-of date")
    parser.add_argument("--names-url", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            redeliver(
                args.source_dir,
                args.names_zip,
                args.output,
                args.version,
                args.names_date,
                args.names_url,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
