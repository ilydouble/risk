"""Export a complete standalone graph view and a per-company information-gap audit."""

import shutil
from collections import Counter, defaultdict

from prepare_uk_basic_information import read_csv
from prepare_uk_financials import sha, write_csv, write_json
from prepare_uk_graph import OUTPUT, graphml
from uk_graph.gleif import stable_id


def group_view(nodes, groups, memberships):
    by_id = {row["id"]: row for row in nodes}
    group_nodes, edges = [], []
    group_members = defaultdict(list)
    for row in memberships:
        group_members[row["group_id"]].append(row["node_id"])
        edges.append(
            {
                "id": "MEMBER:" + stable_id([row["group_id"], row["node_id"]]),
                "source": row["node_id"],
                "target": row["group_id"],
                "relation": "MEMBER_OF_REGISTERED_ADDRESS_GROUP",
                "valid_from": "",
                "valid_to": "",
                "source_system": "Companies House",
                "source_row_sha256": "",
            }
        )
    for group in groups:
        node = dict.fromkeys(nodes[0], "")
        address = by_id[group_members[group["id"]][0]]["snapshot_registered_address"]
        node.update(
            id=group["id"],
            kind="registered_address_group",
            name=address,
            name_source="companies_house_shared_address",
            name_source_date=group["source_date"],
            name_missing=False,
            is_research_company=False,
            observation_count=0,
        )
        group_nodes.append(node)
    return group_nodes, edges


def finalize(output=OUTPUT):
    nodes = list(read_csv(output / "nodes.csv"))
    groups = list(read_csv(output / "groups.csv"))
    memberships = list(read_csv(output / "group-memberships.csv"))
    edges = list(read_csv(output / "edges.csv"))
    group_nodes, member_edges = group_view(nodes, groups, memberships)
    temporary = output / ".graphml-export"
    temporary.mkdir()
    try:
        graphml(temporary, nodes + group_nodes, edges + member_edges)
        (temporary / "enterprise-graph.graphml").replace(
            output / "enterprise-and-address-groups.graphml"
        )
    finally:
        shutil.rmtree(temporary)
    observed = defaultdict(set)
    for filename in ("features.csv", "excluded-case-basic-information.csv"):
        for row in read_csv(output / filename):
            for field in (
                "legal_form",
                "country_of_incorporation",
                "dormant",
                "registered_office_postcode",
                "incorporation_date",
                "sic2007",
            ):
                if row.get("historical_" + field + "_missing") == "False":
                    observed[row["company_id"]].add(field)
    gaps, counts = [], Counter()
    for node in nodes:
        if node["is_research_company"] != "True":
            continue
        fields = observed[node["id"]]
        row = {
            "node_id": node["id"],
            "name_missing": node["name_missing"] == "True",
            "snapshot_basic_missing": node["snapshot_missing"] == "True",
            "unique_gleif_match_missing": not bool(node["lei"]),
            "reference_incorporation_date_missing": not bool(
                node["snapshot_incorporation_date"] or node["gleif_entity_creation_date"]
            ),
            "historical_registry_status_missing": True,
        }
        for field in (
            "legal_form",
            "country_of_incorporation",
            "dormant",
            "registered_office_postcode",
            "incorporation_date",
            "sic2007",
        ):
            row["no_historical_" + field + "_observed"] = field not in fields
        for field, value in row.items():
            if isinstance(value, bool):
                counts[field] += value
        gaps.append(row)
    write_csv(output / "basic-information-gaps.csv", gaps, list(gaps[0]))
    write_json(
        output / "basic-information-gaps.json",
        {
            "researchCompanies": len(gaps),
            "missingCounts": counts,
            "historicalFlagsMeanMissingAcrossAvailableReportsNotAtEveryObservationDate": True,
            "fieldsAreForAuditNotModelFeatures": True,
        },
    )
    write_json(
        output / "full-graph-export.json",
        {
            "file": "enterprise-and-address-groups.graphml",
            "companyNodes": len(nodes),
            "addressGroupNodes": len(group_nodes),
            "parentRelationships": len(edges),
            "membershipEdges": len(member_edges),
            "membershipDirectionIsSerializationOnlyNotOwnership": True,
            "sha256": sha(output / "enterprise-and-address-groups.graphml"),
        },
    )
    company_ids = {row["id"] for row in nodes if row["is_research_company"] == "True"}
    outside = [
        {
            "event_id": row["event_id"],
            "company_id": row["company_id"],
            "reason": "company_not_in_confirmed_research_universe",
        }
        for row in read_csv(output / "events.csv")
        if row["company_id"] not in company_ids
    ]
    write_csv(output / "out-of-scope-events.csv", outside, ["event_id", "company_id", "reason"])


if __name__ == "__main__":
    finalize()
