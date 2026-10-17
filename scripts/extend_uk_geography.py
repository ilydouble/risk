"""Add fixed-vintage administrative groups and SIC intersections to an immutable graph."""

import argparse
import csv
import gzip
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from extend_uk_hyperedges import EVIDENCE_FIELDS, GROUP_FIELDS, raw_records
from fetch_uk_postcode_geography import BASE
from fetch_uk_postcode_geography import OUTPUT as SOURCE
from finalize_uk_graph import group_view
from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from prepare_uk_graph import ROOT, graphml
from uk_graph.geography import (
    administrative_facts,
    canonical_postcode,
    crossed_facts,
    lifecycle_compatible,
)
from uk_graph.gleif import stable_id
from uk_graph.hyperedges import group_id, snapshot_facts

OUTPUT = ROOT / "outputs/uk-research-graph-20261017-v4"
ASSUMPTION = {
    "currentRegistryApproximatesHistoricalObservation": True,
    "acceptedByUser": True,
    "historicalAddressesVerified": False,
    "historicalAdministrativeBoundariesVerified": False,
    "boundaryProjection": "2026 administrative codes projected to earlier observations",
    "graphMembershipBasis": "2026-09-30 registered office snapshot",
    "registeredOfficeIsOperatingLocation": False,
}


def geography_record(postcode, lookup):
    entry = lookup.get(canonical_postcode(postcode), {})
    return entry["candidates"][0] if entry.get("status") == "matched" else None


def observation_geography(row, current_postcode, lookup, names):
    historical = row.get("historical_registered_office_postcode", "")
    historical_ref = geography_record(historical, lookup)
    compatible = bool(
        historical_ref
        and lifecycle_compatible(historical_ref["attributes"], row["observation_date"])
    )
    available = row.get("historical_basic_available_by_assumed", "")
    available_by_observation = bool(available and available <= row["observation_date"])
    usable = compatible and available_by_observation
    chosen = historical_ref if usable else geography_record(current_postcode, lookup)
    attrs = chosen["attributes"] if chosen else {}
    return {
        "sample_id": row["sample_id"],
        "company_id": row["company_id"],
        "observation_date": row["observation_date"],
        "historical_postcode_raw": historical,
        "historical_basic_report_id": row.get("historical_basic_report_id", ""),
        "historical_basic_available_by_assumed": available,
        "historical_postcode_available_by_observation_assumed": available_by_observation,
        "snapshot_postcode_raw": current_postcode,
        "mapping_basis": "historical_financial_report_postcode"
        if usable
        else "current_registry_assumption"
        if chosen
        else "unmapped",
        "historical_postcode_lifecycle_compatible": compatible,
        "mapped_postcode": attrs.get("pcds", ""),
        "postcode_introduced_yyyymm": attrs.get("dointr") or "",
        "postcode_terminated_yyyymm": attrs.get("doterm") or "",
        "local_authority_code": attrs.get("lad26cd", "") if attrs.get("lad26cd") in names else "",
        "local_authority_name": names.get(attrs.get("lad26cd"), ""),
        "region_code": attrs.get("rgn26cd", "") if attrs.get("rgn26cd") in names else "",
        "region_name": names.get(attrs.get("rgn26cd"), ""),
        "ons_country_code": attrs.get("ctry26cd", ""),
        "ons_country_name": names.get(attrs.get("ctry26cd"), ""),
        "directory_vintage": "2026-08",
        "administrative_code_vintage": "2026",
        "historical_address_verified": False,
        "historical_boundary_verified": False,
        "current_registry_assumption_applied": bool(chosen and not usable),
        "fixed_2026_boundary_projection_applied": bool(chosen),
        "source_file": "sources/ons-geography/" + chosen["sourceFile"] if chosen else "",
        "source_object_id": attrs.get("ObjectId", ""),
        "source_attributes_sha256": chosen["attributesSha256"] if chosen else "",
    }


def extend(base, source, output):
    if output.exists() or output.resolve().is_relative_to(base.resolve()):
        raise ValueError("Choose a new version outside the base dataset")
    if not json.loads((base / "validation.json").read_text())["passed"]:
        raise ValueError("Base validation must pass")
    source_manifest = json.loads((source / "source.json").read_text())
    for item in source_manifest["rawFiles"]:
        if sha(source / item["file"]) != item["sha256"]:
            raise ValueError("Raw postcode cache changed")
    for name, digest in source_manifest["files"].items():
        if sha(source / name) != digest:
            raise ValueError("Postcode source changed")
    lookup = json.loads((source / "postcodes.json").read_text())
    names = json.loads((source / "names.json").read_text())
    sic = {
        r["SIC Code"].strip(): r["Description"].strip()
        for r in read_csv(base / "sources/classifications/sic-codes.csv")
    }
    buckets, facts, company_refs, snapshot_postcodes = defaultdict(set), {}, {}, {}
    status_counts = Counter()
    for number, record in raw_records(base / "snapshot-raw-records.jsonl.gz"):
        company = record["company_id"]
        postcode = record["row"].get("RegAddress.PostCode", "")
        snapshot_postcodes[company] = postcode
        reference = geography_record(postcode, lookup)
        status_counts[
            lookup.get(canonical_postcode(postcode), {}).get("status", "invalid_or_missing")
        ] += 1
        if not reference:
            continue
        geo = administrative_facts(reference["attributes"], names)
        industry = snapshot_facts(record["row"], sic)
        company_facts = geo + list(crossed_facts(industry, geo))
        if not company_facts:
            continue
        company_refs[company] = {
            "company_id": company,
            "snapshot_record_number": number,
            "snapshot_row_sha256": record["row_sha256"],
            "snapshot_postcode_raw": postcode,
            "snapshot_sic_fields": {
                k: v for k, v in record["row"].items() if k.startswith("SICCode.")
            },
            "postcode_reference": reference,
            "name_source_file": "sources/ons-geography/name-response.json",
            "name_source_sha256": source_manifest["files"]["name-response.json"],
        }
        for fact in company_facts:
            key = fact["kind"], fact["value"]
            buckets[key].add(company)
            facts[key] = fact
    admitted = {k: v for k, v in buckets.items() if len(v) >= 2}
    skip = {
        "delivery-manifest.json",
        "validation.json",
        "README.md",
        "enterprise-and-hyperedges.graphml",
        "full-graph-export.json",
        "graph-summary.json",
        "hyperedge-type-summary.csv",
    }
    shutil.copytree(
        base,
        output,
        ignore=lambda directory, files: [x for x in files if Path(directory) == base and x in skip],
    )
    provenance = output / "provenance/v3"
    provenance.mkdir(parents=True, exist_ok=True)
    for name in skip | {"graph-manifest.json", "hyperedge-manifest.json", "source-manifest.json"}:
        if (base / name).is_file() and not name.endswith(".graphml"):
            shutil.copyfile(base / name, provenance / name)
    shutil.copytree(source, output / "sources/ons-geography")
    source_sha = sha(source / "source.json")
    groups = list(read_csv(base / "groups.csv"))
    by_key = {(r["kind"], r["value"]): r["id"] for r in groups}
    for key, members in sorted(admitted.items()):
        fact = facts[key]
        crossed = "components" in fact
        identifier = group_id(key[0], key[1], "2026-09-30|ONSPD202608|LAD2026")
        by_key[key] = identifier
        groups.append(
            dict(
                zip(
                    GROUP_FIELDS,
                    [
                        identifier,
                        key[0],
                        len(members),
                        "Companies House + ONS",
                        "2026-09-30",
                        source_sha,
                        False,
                        key[1],
                        fact["label"],
                        "attribute",
                        "industry_administrative_geography"
                        if crossed
                        else "administrative_geography",
                        "intersection" if crossed else key[0],
                        "",
                        "MEMBER_OF_" + key[0].upper(),
                        sha(base / "sources/classifications/sic-codes.csv") if crossed else "",
                        "intersection_of_declared_industry_and_administrative_code"
                        if crossed
                        else "official_postcode_to_2026_administrative_code",
                    ],
                    strict=True,
                )
            )
        )
    components = []
    for key in admitted:
        for component in facts[key].get("components", []):
            component_id = by_key[(component["kind"], component["value"])]
            components.append(
                {
                    "group_id": by_key[key],
                    "component_group_id": component_id,
                    "dimension": component["kind"],
                }
            )
    write_csv(output / "groups.csv", groups, GROUP_FIELDS)
    write_csv(
        output / "group-components.csv", components, ["group_id", "component_group_id", "dimension"]
    )
    evidence_refs = {}
    with gzip.open(output / "company-geography-evidence.jsonl.gz", "wt") as stream:
        for number, (company, record) in enumerate(sorted(company_refs.items()), 1):
            evidence_refs[company] = (number, stable_id(record))
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (
        (output / "group-memberships.csv").open("a", encoding="utf-8", newline="") as stream,
        (output / "membership-evidence.csv").open(
            "a", encoding="utf-8", newline=""
        ) as evidence_stream,
    ):
        writer = csv.DictWriter(stream, fieldnames=["group_id", "node_id"])
        evidence_writer = csv.DictWriter(evidence_stream, fieldnames=EVIDENCE_FIELDS)
        for key, members in sorted(admitted.items()):
            for company in sorted(members):
                writer.writerow({"group_id": by_key[key], "node_id": company})
                number, digest = evidence_refs[company]
                evidence_writer.writerow(
                    {
                        "group_id": by_key[key],
                        "node_id": company,
                        "source_file": "company-geography-evidence.jsonl.gz",
                        "source_record_number": number,
                        "source_record_id": company,
                        "source_fields": json.dumps(["company_id"]),
                        "source_values": json.dumps([company]),
                        "source_row_sha256": digest,
                    }
                )
    observation_counts = Counter()
    observation_coverage = Counter()

    def observations():
        for row in read_csv(base / "features.csv"):
            result = observation_geography(
                row, snapshot_postcodes.get(row["company_id"], ""), lookup, names
            )
            observation_counts[result["mapping_basis"]] += 1
            observation_coverage["local_authority"] += bool(result["local_authority_code"])
            observation_coverage["region"] += bool(result["region_code"])
            yield result

    iterator = observations()
    first = next(iterator)
    import itertools

    write_csv(output / "observation-geography.csv", itertools.chain([first], iterator), list(first))
    nodes, edges = list(read_csv(base / "nodes.csv")), list(read_csv(base / "edges.csv"))
    memberships = list(read_csv(output / "group-memberships.csv"))
    group_nodes, member_edges = group_view(nodes, groups, memberships)
    temporary = output / ".graphml-export"
    temporary.mkdir()
    graphml(temporary, nodes + group_nodes, edges + member_edges)
    (temporary / "enterprise-graph.graphml").replace(output / "enterprise-and-hyperedges.graphml")
    temporary.rmdir()
    type_counts = Counter(r["kind"] for r in groups)
    member_counts = Counter()
    for group in groups:
        member_counts[group["kind"]] += int(group["member_count"])
    write_csv(
        output / "hyperedge-type-summary.csv",
        [
            {"kind": k, "groups": v, "memberships": member_counts[k]}
            for k, v in sorted(type_counts.items())
        ],
        ["kind", "groups", "memberships"],
    )
    summary = {
        "companyNodes": len(nodes),
        "researchCompanies": sum(n["is_research_company"] == "True" for n in nodes),
        "parentRelationships": len(edges),
        "groups": len(groups),
        "memberships": len(memberships),
        "newGroups": len(admitted),
        "newMemberships": sum(map(len, admitted.values())),
        "newKinds": sorted({k[0] for k in admitted}),
        "snapshotPostcodeMapping": status_counts,
        "observationMapping": observation_counts,
        "observationAdministrativeCoverage": observation_coverage,
        "staticAdministrativeCoverage": {
            kind: len(
                set().union(*(members for key, members in admitted.items() if key[0] == kind))
            )
            for kind in ("admin_local_authority", "admin_region")
        },
        "researchAssumption": ASSUMPTION,
        "singletonGroupsNotEmitted": sum(len(v) == 1 for v in buckets.values()),
        "financialHistoryExtension": {
            "directory": "uk-financial-history-20261017-v1",
            "zipSha256": "29c98dd6e004ec9fdab86bb88618529430fd8593b42fc596c52984b6aeee5e00",
            "join": "company_id and sample_id; retain its multi-period features",
        },
    }
    write_json(output / "geography-summary.json", summary)
    write_json(output / "graph-summary.json", summary)
    write_json(
        output / "geography-manifest.json",
        {
            "sourceSha256": source_sha,
            "sourceDirectory": "sources/ons-geography",
            "assumption": ASSUMPTION,
            "staticGraphUsesHistoricalFinancialPostcodes": False,
            "observationGeographyIsSeparateSidecar": True,
        },
    )
    for filename in ("graph-manifest.json", "hyperedge-manifest.json"):
        manifest = json.loads((base / filename).read_text())
        manifest.update(
            parentVersion=base.name,
            groupCount=len(groups),
            membershipCount=len(memberships),
            geographyExtension="geography-manifest.json",
            researchAssumption=ASSUMPTION,
        )
        if filename == "graph-manifest.json":
            manifest.update(
                format="uk-research-graph-geography-v4",
                hyperedgeKinds=sorted(type_counts),
                postcodeDirectoryGeocodingVerified=True,
                historicalRelationshipsVerified=False,
                allHyperedgesHistoricalPredictionEligible=False,
            )
        write_json(output / filename, manifest)
    write_json(
        output / "full-graph-export.json",
        {
            "file": "enterprise-and-hyperedges.graphml",
            "companyNodes": len(nodes),
            "groupNodes": len(groups),
            "parentRelationships": len(edges),
            "membershipEdges": len(memberships),
            "sha256": sha(output / "enterprise-and-hyperedges.graphml"),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    extend(args.base, args.source, args.output)
