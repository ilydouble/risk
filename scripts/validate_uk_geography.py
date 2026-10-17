"""Independently verify preservation, official evidence, exact intersections and graph export."""

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree.ElementTree import iterparse

from extend_uk_geography import BASE, OUTPUT
from extend_uk_hyperedges import raw_records
from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_json
from uk_graph.geography import canonical_postcode
from uk_graph.gleif import stable_id


def validate(base, output):
    changed = {
        "groups.csv",
        "group-memberships.csv",
        "membership-evidence.csv",
        "graph-manifest.json",
        "hyperedge-manifest.json",
        "delivery-manifest.json",
        "validation.json",
        "README.md",
        "enterprise-and-hyperedges.graphml",
        "full-graph-export.json",
        "graph-summary.json",
        "hyperedge-type-summary.csv",
    }
    preserved = {}
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if len(relative.parts) == 1 and path.name in changed:
            continue
        assert sha(path) == sha(output / relative), str(relative)
        preserved[str(relative)] = sha(path)
    groups = {r["id"]: r for r in read_csv(output / "groups.csv")}
    old_groups = {r["id"]: r for r in read_csv(base / "groups.csv")}
    assert all(groups[k] == v for k, v in old_groups.items())
    assert len(groups) == sum(1 for _ in read_csv(output / "groups.csv"))
    nodes = {r["id"] for r in read_csv(output / "nodes.csv")}
    members = defaultdict(set)
    for r in read_csv(output / "group-memberships.csv"):
        assert r["group_id"] in groups and r["node_id"] in nodes
        assert r["node_id"] not in members[r["group_id"]]
        members[r["group_id"]].add(r["node_id"])
    for r in read_csv(base / "group-memberships.csv"):
        assert r["node_id"] in members[r["group_id"]]
    for key, group in groups.items():
        assert int(group["member_count"]) == len(members[key]) >= 2
        assert group["historical_prediction_eligible"] == "False"
    # Prefix preservation also proves all original evidence rows and membership multiplicities.
    for name in ("membership-evidence.csv", "group-memberships.csv"):
        with (base / name).open("rb") as left, (output / name).open("rb") as right:
            while block := left.read(1024 * 1024):
                assert block == right.read(len(block))
    components = defaultdict(list)
    for r in read_csv(output / "group-components.csv"):
        assert r["group_id"] in groups and r["component_group_id"] in groups
        components[r["group_id"]].append(r["component_group_id"])
    for key in groups.keys() - old_groups.keys():
        if "_x_" in groups[key]["kind"]:
            assert len(components[key]) == len(set(components[key])) == 2
            a, b = components[key]
            assert groups[key]["kind"] == groups[a]["kind"] + "_x_" + groups[b]["kind"]
            assert groups[key]["value"] == groups[a]["value"] + "|" + groups[b]["value"]
            assert members[key] == members[a] & members[b]
        else:
            assert groups[key]["kind"] in {"admin_local_authority", "admin_region"}
    source = output / "sources/ons-geography"
    manifest = json.loads((source / "source.json").read_text())
    geo_manifest = json.loads((output / "geography-manifest.json").read_text())
    assert geo_manifest["sourceSha256"] == sha(source / "source.json")
    assert geo_manifest["assumption"]["currentRegistryApproximatesHistoricalObservation"] is True
    assert geo_manifest["assumption"]["historicalAddressesVerified"] is False
    assert geo_manifest["assumption"]["historicalAdministrativeBoundariesVerified"] is False
    for filename, digest in manifest["files"].items():
        assert sha(source / filename) == digest
    for r in manifest["rawFiles"]:
        assert sha(source / r["file"]) == r["sha256"]
    names_response = json.loads((source / "name-response.json").read_text())
    names = json.loads((source / "names.json").read_text())
    official_names = {}
    for feature in names_response["features"]:
        for prefix in ("LAD", "RGN", "CTRY"):
            attrs = feature["attributes"]
            code, name = attrs.get(prefix + "26CD"), attrs.get(prefix + "26NM")
            if code and name and "999999" not in code:
                official_names[code] = name
    assert names == official_names
    raw_attrs = {}
    requested_postcodes = set()
    for r in manifest["rawFiles"]:
        with gzip.open(source / r["file"], "rt") as stream:
            response = json.load(stream)
        assert response["epoch"] == manifest["postcodeEpoch"]
        assert not requested_postcodes.intersection(response["requestedPostcodes"])
        requested_postcodes.update(response["requestedPostcodes"])
        for p, page in enumerate(response["pages"]):
            for f, feature in enumerate(page["features"]):
                raw_attrs[(r["file"], p, f)] = feature["attributes"]
    lookup = json.loads((source / "postcodes.json").read_text())
    assert requested_postcodes == lookup.keys()
    for postcode, entry in lookup.items():
        candidates = entry["candidates"]
        assert entry["status"] == (
            "matched" if len(candidates) == 1 else "ambiguous" if candidates else "not_found"
        )
        for ref in candidates:
            attrs = raw_attrs[(ref["sourceFile"], ref["page"], ref["feature"])]
            assert attrs == ref["attributes"] and stable_id(attrs) == ref["attributesSha256"]
            assert canonical_postcode(attrs["pcds"]) == postcode
    evidence = {}
    snapshot = {
        r["company_id"]: (n, r) for n, r in raw_records(output / "snapshot-raw-records.jsonl.gz")
    }
    expected_admin = defaultdict(set)
    for company, (_, raw) in snapshot.items():
        postcode = canonical_postcode(raw["row"].get("RegAddress.PostCode", ""))
        entry = lookup.get(postcode, {})
        if entry.get("status") != "matched":
            continue
        attrs = entry["candidates"][0]["attributes"]
        for field, kind in (("lad26cd", "admin_local_authority"), ("rgn26cd", "admin_region")):
            code = attrs.get(field)
            if code in names and "999999" not in code:
                expected_admin[(kind, code)].add(company)
    expected_admin = {k: v for k, v in expected_admin.items() if len(v) >= 2}
    actual_admin = {
        (r["kind"], r["value"]): members[k]
        for k, r in groups.items()
        if r["kind"] in {"admin_local_authority", "admin_region"}
    }
    assert actual_admin == expected_admin
    industry_by_company = defaultdict(list)
    for key, group in old_groups.items():
        if group["kind"] in {"industry_sic_division", "industry_sic_subclass"}:
            for company in members[key]:
                industry_by_company[company].append(key)
    expected_cross = defaultdict(set)
    for key, group in groups.items():
        if group["kind"] not in {"admin_local_authority", "admin_region"}:
            continue
        for company in members[key]:
            for industry_id in industry_by_company[company]:
                expected_cross[(industry_id, key)].add(company)
    expected_cross = {k: v for k, v in expected_cross.items() if len(v) >= 2}
    actual_cross = {tuple(parts): members[key] for key, parts in components.items()}
    assert len(actual_cross) == len(components)
    assert actual_cross == expected_cross
    with gzip.open(output / "company-geography-evidence.jsonl.gz", "rt") as stream:
        for number, line in enumerate(stream, 1):
            record = json.loads(line)
            company = record["company_id"]
            n, raw = snapshot[company]
            assert record["snapshot_record_number"] == n
            assert record["snapshot_row_sha256"] == raw["row_sha256"]
            assert record["snapshot_postcode_raw"] == raw["row"].get("RegAddress.PostCode", "")
            assert record["snapshot_sic_fields"] == {
                k: v for k, v in raw["row"].items() if k.startswith("SICCode.")
            }
            ref = record["postcode_reference"]
            attrs = raw_attrs[(ref["sourceFile"], ref["page"], ref["feature"])]
            assert attrs == ref["attributes"] and stable_id(attrs) == ref["attributesSha256"]
            assert canonical_postcode(record["snapshot_postcode_raw"]) == canonical_postcode(
                attrs["pcds"]
            )
            evidence[company] = (number, stable_id(record), attrs)
    new_evidence_pairs = set()
    for r in read_csv(output / "membership-evidence.csv"):
        key, company = r["group_id"], r["node_id"]
        if key in old_groups:
            continue
        assert company in members[key]
        number, digest, attrs = evidence[company]
        assert r["source_file"] == "company-geography-evidence.jsonl.gz"
        assert int(r["source_record_number"]) == number and r["source_row_sha256"] == digest
        assert json.loads(r["source_fields"]) == ["company_id"]
        assert json.loads(r["source_values"]) == [company]
        field = "rgn26cd" if groups[key]["kind"].endswith("admin_region") else "lad26cd"
        assert groups[key]["value"].split("|")[-1] == attrs[field]
        assert attrs[field] in names and "999999" not in attrs[field]
        assert (key, company) not in new_evidence_pairs
        new_evidence_pairs.add((key, company))
    new_evidence_count = len(new_evidence_pairs)
    assert new_evidence_count == sum(len(v) for k, v in members.items() if k not in old_groups)
    observations = {
        r["sample_id"]: (
            r["company_id"],
            r["observation_date"],
            r.get("historical_registered_office_postcode", ""),
            r.get("historical_basic_available_by_assumed", ""),
            r.get("historical_basic_report_id", ""),
        )
        for r in read_csv(base / "features.csv")
    }
    needed_postcodes = {
        canonical_postcode(r[1]["row"].get("RegAddress.PostCode", "")) for r in snapshot.values()
    }
    needed_postcodes.update(canonical_postcode(r[2]) for r in observations.values())
    needed_postcodes.discard("")
    assert requested_postcodes == needed_postcodes
    mapped = Counter()
    mapped_coverage = Counter()
    count = 0
    for r in read_csv(output / "observation-geography.csv"):
        assert r["sample_id"] in observations
        company, date, historical, available, report = observations.pop(r["sample_id"])
        assert (r["company_id"], r["observation_date"], r["historical_postcode_raw"]) == (
            company,
            date,
            historical,
        )
        current = snapshot.get(company, (None, {"row": {}}))[1]["row"].get(
            "RegAddress.PostCode", ""
        )
        assert r["snapshot_postcode_raw"] == current
        historical_entry = lookup.get(canonical_postcode(historical), {})
        hist = historical_entry.get("candidates", [])
        attrs = hist[0]["attributes"] if historical_entry.get("status") == "matched" else {}
        month = int(date[:7].replace("-", ""))
        compatible = bool(
            attrs.get("dointr")
            and attrs["dointr"] <= month
            and (not attrs.get("doterm") or attrs["doterm"] >= month)
        )
        assert r["historical_basic_available_by_assumed"] == available
        assert r["historical_basic_report_id"] == report
        available_by_observation = bool(available and available <= date)
        assert r["historical_postcode_available_by_observation_assumed"] == str(
            available_by_observation
        )
        if compatible and available_by_observation:
            assert r["mapping_basis"] == "historical_financial_report_postcode"
            ref = hist[0]
        else:
            current_entry = lookup.get(canonical_postcode(current), {})
            ref = (
                current_entry["candidates"][0] if current_entry.get("status") == "matched" else None
            )
            assert r["mapping_basis"] == ("current_registry_assumption" if ref else "unmapped")
        assert r["historical_postcode_lifecycle_compatible"] == str(compatible)
        if ref:
            attrs = ref["attributes"]
            assert r["mapped_postcode"] == attrs["pcds"]
            assert r["source_attributes_sha256"] == stable_id(attrs)
            for field, target in (("lad26cd", "local_authority"), ("rgn26cd", "region")):
                code = attrs.get(field, "") if attrs.get(field) in names else ""
                assert r[target + "_code"] == code
                assert r[target + "_name"] == names.get(code, "")
        assert r["historical_address_verified"] == r["historical_boundary_verified"] == "False"
        if r["mapped_postcode"]:
            assert r["fixed_2026_boundary_projection_applied"] == "True"
        mapped[r["mapping_basis"]] += 1
        mapped_coverage["local_authority"] += bool(r["local_authority_code"])
        mapped_coverage["region"] += bool(r["region_code"])
        count += 1
    assert not observations
    summary = json.loads((output / "geography-summary.json").read_text())
    assert summary["companyNodes"] == len(nodes)
    assert summary["groups"] == len(groups)
    assert summary["memberships"] == sum(map(len, members.values()))
    assert summary["newGroups"] == len(groups.keys() - old_groups.keys())
    assert summary["newMemberships"] == new_evidence_count
    assert summary["observationMapping"] == mapped
    assert summary["observationAdministrativeCoverage"] == mapped_coverage
    xml_nodes, xml_edges = set(), set()
    ordinary_edges = {r["id"]: r for r in read_csv(output / "edges.csv")}
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    for _event, element in iterparse(output / "enterprise-and-hyperedges.graphml", events=("end",)):
        if element.tag == ns + "node":
            assert element.attrib["id"] not in xml_nodes
            xml_nodes.add(element.attrib["id"])
            element.clear()
        elif element.tag == ns + "edge":
            source_id, target = element.attrib["source"], element.attrib["target"]
            assert source_id in nodes
            if target in groups:
                assert source_id in members[target]
                assert element.attrib["id"] == "MEMBER:" + stable_id([target, source_id])
                relation = groups[target]["membership_relation"]
            else:
                assert target in nodes
                original = ordinary_edges[element.attrib["id"]]
                assert (source_id, target) == (original["source"], original["target"])
                relation = original["relation"]
            assert element.find(ns + "data[@key='edge_relation']").text == relation
            assert element.attrib["id"] not in xml_edges
            xml_edges.add(element.attrib["id"])
            element.clear()
    assert xml_nodes == nodes | groups.keys()
    assert len(xml_edges) == sum(map(len, members.values())) + sum(
        1 for _ in read_csv(output / "edges.csv")
    )
    result = {
        "passed": True,
        "preservedFiles": len(preserved),
        "companyNodes": len(nodes),
        "groups": len(groups),
        "memberships": sum(map(len, members.values())),
        "newMembershipEvidence": new_evidence_count,
        "observations": count,
        "observationMapping": mapped,
        "exactCrossIntersectionsVerified": len(components),
        "historicalVerificationClaimed": False,
        "preservedSha256": preserved,
    }
    result["validatedSha256"] = {
        str(path.relative_to(output)): sha(path)
        for path in output.rglob("*")
        if path.is_file()
        and str(path.relative_to(output)) not in {"validation.json", "delivery-manifest.json"}
    }
    write_json(output / "validation.json", result)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"preservedSha256", "validatedSha256"}},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    validate(args.base, args.output)
