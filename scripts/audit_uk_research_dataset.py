"""Read-only descriptive audit of a delivered UK research graph, using the stdlib."""

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    result = {"n": len(values), "min": values[0], "max": values[-1]}
    for key, fraction in [
        ("p05", 0.05),
        ("p25", 0.25),
        ("median", 0.5),
        ("p75", 0.75),
        ("p95", 0.95),
        ("p99", 0.99),
    ]:
        offset = (len(values) - 1) * fraction
        lo = int(offset)
        hi = min(lo + 1, len(values) - 1)
        result[key] = values[lo] + (values[hi] - values[lo]) * (offset - lo)
    return result


def write_csv(path, records):
    if not records:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = list(dict.fromkeys(key for record in records for key in record))
        writer = csv.DictWriter(stream, fieldnames=fields, restval=0)
        writer.writeheader()
        writer.writerows(records)


def original_dimension_candidates(raw, period_end):
    """Find review candidates, without relaxing the production financial parser."""
    if b"<!ENTITY" in raw.upper():
        return {"status": "entity_declaration_skipped"}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {"status": "strict_xml_parse_failed"}

    def local(value):
        return value.rsplit("}", 1)[-1].rsplit(":", 1)[-1]

    contexts = set()
    for node in root.iter():
        if local(node.tag) != "context":
            continue
        descendants = list(node.iter())
        end = next((n.text for n in descendants if local(n.tag) in {"instant", "endDate"}), "")
        dimensions = [n for n in descendants if local(n.tag) in {"explicitMember", "typedMember"}]
        if (
            end == period_end
            and dimensions
            and all(
                local(n.tag) == "explicitMember"
                and (local(n.get("dimension", "")), local(n.text or ""))
                == ("OriginalRevisedDataDimension", "Original")
                for n in dimensions
            )
        ):
            contexts.add(node.get("id"))
    concepts = set()
    for node in root.iter():
        name = local(node.get("name", node.tag))
        if (
            node.get("contextRef") in contexts
            and local(node.tag).lower() == "nonfraction"
            and name
            in {
                "CurrentAssets",
                "FixedAssets",
                "CashBankOnHand",
                "Equity",
                "NetAssetsLiabilities",
                "TotalAssetsLessCurrentLiabilities",
                "TurnoverRevenue",
                "ProfitLoss",
            }
            and "".join(node.itertext()).strip()
        ):
            concepts.add(name)
    return {"status": "inspected", "concepts": sorted(concepts)}


class Components:
    def __init__(self, ids):
        self.parent = dict.fromkeys(ids)
        self.sizes = dict.fromkeys(ids, 1)

    def root(self, node):
        if self.parent[node] is None:
            return node
        self.parent[node] = self.root(self.parent[node])
        return self.parent[node]

    def join(self, left, right):
        left, right = self.root(left), self.root(right)
        if left == right:
            return
        if self.sizes[left] < self.sizes[right]:
            left, right = right, left
        self.parent[right] = left
        self.sizes[left] += self.sizes[right]

    def summary(self, research):
        sizes = Counter(self.root(node) for node in research)
        return {
            "research_components": len(sizes),
            "research_singletons": sum(n == 1 for n in sizes.values()),
            "largest_research_component": max(sizes.values()),
            "top10_sizes": sorted(sizes.values(), reverse=True)[:10],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--financial-facts", type=Path)
    args = parser.parse_args()
    src, out = args.dataset, args.output
    if src.resolve() == out.resolve() or src.resolve() in out.resolve().parents:
        parser.error("audit output must be outside the immutable dataset")
    out.mkdir(parents=True, exist_ok=True)
    result = {"dataset": str(src.resolve()), "quantile_method": "linear interpolation at (n-1)*p"}

    manifest = json.loads((src / "delivery-manifest.json").read_text())
    failures = []
    for name, expected in manifest["files"].items():
        path = src / name
        if not path.is_file():
            failures.append({"file": name, "reason": "missing"})
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            failures.append({"file": name, "reason": "digest_or_size"})
    result["integrity"] = {"checked_files": len(manifest["files"]), "failures": failures}
    print("Integrity checked", flush=True)

    nodes = {r["id"]: r for r in rows(src / "nodes.csv")}
    research = {key for key, r in nodes.items() if r["is_research_company"] == "True"}
    labels = {r["sample_id"]: r for r in rows(src / "labels.csv")}
    roles = defaultdict(set)
    for r in labels.values():
        roles[r["company_id"]].add(r["role"])
    excluded = list(rows(src / "excluded-cases.csv"))
    for r in excluded:
        roles[r["company_id"]].add("excluded_event")
    result["cohort"] = {
        "research_companies": len(research),
        "company_nodes": len(nodes),
        "samples": len(labels),
        "roles_samples": dict(Counter(r["role"] for r in labels.values())),
        "distinct_sample_companies": len({r["company_id"] for r in labels.values()}),
        "company_role_combinations": dict(Counter("+".join(sorted(roles[c])) for c in research)),
        "excluded_event_rows": len(excluded),
        "excluded_reasons": dict(Counter(r["exclusion_reason"] for r in excluded)),
    }
    year_stats = defaultdict(Counter)
    label_checks = Counter()
    pair_roles = defaultdict(list)
    event_types = Counter()
    event_quality = defaultdict(Counter)
    event_years = defaultdict(Counter)
    for r in labels.values():
        year_stats[r["observation_month"][:4]][r["role"]] += 1
        pair_roles[r["pair_id"]].append(r)
        for flag in ["historical_register_status_verified", "all_adverse_states_verified"]:
            label_checks[flag + ":" + r[flag]] += 1
    label_checks["invalid_pair_size_roles_or_month"] = sum(
        len(pair) != 2
        or {r["role"] for r in pair} != {"case", "control"}
        or len({r["observation_month"] for r in pair}) != 1
        for pair in pair_roles.values()
    )
    for r in rows(src / "events.csv"):
        event_types[r["event_type"]] += 1
        event_years[r["reference_month"][:4]][r["event_type"]] += 1
        for field in [
            "event_role",
            "register_location",
            "date_precision",
            "reference_date_basis",
            "is_bulk_status",
            "company_id_status",
            "label_candidate",
        ]:
            event_quality[field][r[field]] += 1
        for field in ["event_date", "published_at", "duplicate_of_event_id", "review_reasons"]:
            event_quality[field]["present" if r[field] else "missing"] += 1
    result["events"] = {
        "rows": sum(event_types.values()),
        "types": event_types,
        "quality": event_quality,
        "years": event_years,
        "linked_rows": sum(1 for _ in rows(src / "event-node-links.csv")),
        "out_of_scope_rows": sum(1 for _ in rows(src / "out-of-scope-events.csv")),
    }
    result["label_checks"] = label_checks

    first_feature = next(rows(src / "features.csv"))
    metrics = [
        key.removesuffix("_missing")
        for key in first_feature
        if key.endswith("_missing")
        and not key.startswith(("historical_", "financial_", "company_"))
    ]
    historical = [
        key.removesuffix("_missing")
        for key in first_feature
        if key.startswith("historical_") and key.endswith("_missing")
    ]
    values = defaultdict(list)
    field_counts = defaultdict(Counter)
    basic_values = defaultdict(Counter)
    age = defaultdict(list)
    fin_counts = defaultdict(Counter)
    by_role = defaultdict(Counter)
    coverage_companies = defaultdict(set)
    checks = Counter()
    anomalies = []
    missing_report_ids = Counter()
    for r in rows(src / "features.csv"):
        label = labels[r["sample_id"]]
        role = label["role"]
        node = nodes[r["company_id"]]
        by_role[role]["samples"] += 1
        for key, valid in [
            ("current_snapshot", node["snapshot_missing"] == "False"),
            ("lei", bool(node["lei"])),
        ]:
            by_role[role][key] += valid
        populated = 0
        for metric in metrics:
            val = r[metric]
            checks["metric_missing_flag_disagreement"] += (val == "") != (
                r[metric + "_missing"] == "True"
            )
            if not val:
                continue
            field_counts[metric][role] += 1
            number = float(val)
            if not math.isfinite(number):
                anomalies.append(
                    {
                        "sample_id": r["sample_id"],
                        "field": metric,
                        "value": val,
                        "reason": "nonfinite",
                    }
                )
                continue
            populated += 1
            values[metric].append(number)
            field_counts[metric]["negative"] += number < 0
            field_counts[metric]["zero"] += number == 0
            if metric == "average_employees" and (number < 0 or not number.is_integer()):
                anomalies.append(
                    {
                        "sample_id": r["sample_id"],
                        "field": metric,
                        "value": val,
                        "reason": "negative_or_fractional_employees_review",
                    }
                )
        fin_counts[role][str(populated)] += 1
        by_role[role]["any_financial_metric"] += populated > 0
        by_role[role]["any_monetary_metric"] += any(
            r[k] for k in metrics if k != "average_employees"
        )
        by_role[role]["any_profit_or_revenue"] += any(
            r[k] for k in ["revenue", "profit_loss", "profit_before_tax", "operating_profit_loss"]
        )
        by_role[role]["financial_currency:" + r["financial_currency"]] += 1
        year = label["observation_month"][:4]
        year_stats[year][role + "_snapshot"] += node["snapshot_missing"] == "False"
        year_stats[year][role + "_any_financial"] += populated > 0
        year_stats[year][role + "_financial_missing_flag"] += r["financial_missing"] == "True"
        by_role[role]["missing_reason:" + r["financial_missing_reason"]] += 1
        if r["financial_missing"] == "True":
            missing_report_ids[r["baseline_report_id"]] += 1
        for key, valid in {
            "can_derive_assets_fixed_plus_current": bool(r["fixed_assets"] and r["current_assets"]),
            "can_derive_assets_total_less_plus_current_liabilities": bool(
                r["total_assets_less_current_liabilities"] and r["current_liabilities"]
            ),
            "can_derive_current_ratio": bool(
                r["current_assets"]
                and r["current_liabilities"]
                and float(r["current_liabilities"]) > 0
            ),
            "can_derive_cash_ratio": bool(
                r["cash"] and r["current_liabilities"] and float(r["current_liabilities"]) > 0
            ),
            "can_derive_profit_margin": bool(
                r["profit_loss"] and r["revenue"] and float(r["revenue"]) > 0
            ),
        }.items():
            by_role[role][key] += valid
        if r["average_employees"]:
            employees = float(r["average_employees"])
            for key, invalid in {
                "employees_negative": employees < 0,
                "employees_fractional_nonnegative": employees >= 0 and not employees.is_integer(),
                "employees_over_100000_review": employees > 100000,
                "employees_equals_numeric_company_id": r["company_id"].isdigit()
                and employees == int(r["company_id"]),
            }.items():
                by_role[role][key] += invalid
                if invalid and key in {
                    "employees_over_100000_review",
                    "employees_equals_numeric_company_id",
                }:
                    anomalies.append(
                        {
                            "sample_id": r["sample_id"],
                            "field": "average_employees",
                            "value": r["average_employees"],
                            "reason": key,
                        }
                    )
        for field in historical:
            if r[field]:
                by_role[role][field] += 1
                coverage_companies[field].add(r["company_id"])
                if field in [
                    "historical_legal_form",
                    "historical_country_of_incorporation",
                    "historical_dormant",
                ]:
                    basic_values[field][r[field]] += 1
        age[role].append(int(r["report_age_days"]))
        by_role[role]["report_older_than_365_days"] += int(r["report_age_days"]) > 365
        by_role[role]["report_older_than_730_days"] += int(r["report_age_days"]) > 730
        checks["report_available_after_observation"] += (
            r["historical_basic_available_by_assumed"] > r["observation_date"]
        )
        checks["report_period_after_observation"] += (
            r["historical_basic_period_end"] > r["observation_date"]
        )
        checks["observation_month_mismatch"] += (
            r["observation_date"][:7] != label["observation_month"]
        )
        if r["historical_country_of_incorporation"] == "AllCountries":
            by_role[role]["historical_country_aggregate_AllCountries"] += 1
    write_csv(
        out / "financial-coverage.csv",
        [
            {
                "metric": metric,
                "nonmissing": len(values[metric]),
                "case": field_counts[metric]["case"],
                "control": field_counts[metric]["control"],
                "negative": field_counts[metric]["negative"],
                "zero": field_counts[metric]["zero"],
                **distribution(values[metric]),
            }
            for metric in metrics
        ],
    )
    write_csv(
        out / "year-coverage.csv",
        [{"observation_year": year, **counts} for year, counts in sorted(year_stats.items())],
    )
    write_csv(out / "financial-anomalies.csv", anomalies)
    result["features"] = {
        "metrics": metrics,
        "metric_counts": field_counts,
        "populated_metric_histogram": fin_counts,
        "by_role": by_role,
        "basic_value_distributions": basic_values,
        "report_age_days": {k: distribution(v) for k, v in age.items()},
        "checks": checks,
        "numeric_anomaly_rows": len(anomalies),
    }
    result["years"] = year_stats
    print("Cohort, events and features audited", flush=True)

    groups = {r["id"]: r for r in rows(src / "groups.csv")}
    members = defaultdict(list)
    node_types = defaultdict(set)
    degrees = Counter()
    unique_membership = set()
    membership_checks = Counter()
    for r in rows(src / "group-memberships.csv"):
        gid, node = r["group_id"], r["node_id"]
        membership_checks["unknown_endpoint"] += gid not in groups or node not in nodes
        membership_checks["duplicate"] += (gid, node) in unique_membership
        unique_membership.add((gid, node))
        members[gid].append(node)
        node_types[node].add(groups[gid]["kind"])
        degrees[node] += 1
    edges = list(rows(src / "edges.csv"))
    ordinary_degree = Counter()
    for r in edges:
        ordinary_degree[r["source"]] += 1
        ordinary_degree[r["target"]] += 1
    per_type = defaultdict(list)
    for gid, group in groups.items():
        per_type[group["kind"]].append(gid)
        membership_checks["member_count_disagreement"] += int(group["member_count"]) != len(
            members[gid]
        )
    company_groups = defaultdict(lambda: defaultdict(list))
    for gid, company_ids in members.items():
        kind = groups[gid]["kind"]
        if kind in {
            "industry_sic_division",
            "industry_sic_subclass",
            "postcode_area",
            "postcode_district",
        }:
            for company_id in company_ids:
                company_groups[company_id][kind].append(gid)
    potential_groups = []
    for industry, geography in [
        ("industry_sic_division", "postcode_district"),
        ("industry_sic_subclass", "postcode_area"),
        ("industry_sic_subclass", "postcode_district"),
    ]:
        combinations = defaultdict(set)
        for company_id, kinds in company_groups.items():
            for left in kinds[industry]:
                for right in kinds[geography]:
                    combinations[left, right].add(company_id)
        retained = [company_ids for company_ids in combinations.values() if len(company_ids) >= 2]
        potential_groups.append(
            {
                "candidate": industry + "_x_" + geography,
                "groups_min_two": len(retained),
                "memberships": sum(map(len, retained)),
                "research_companies": len(set().union(*retained)),
                "size_at_most_50_groups": sum(len(company_ids) <= 50 for company_ids in retained),
                **distribution([len(company_ids) for company_ids in retained]),
            }
        )
    result["potential_compound_hyperedges_current_snapshot_only"] = potential_groups
    write_csv(out / "potential-compound-hyperedges.csv", potential_groups)
    scenarios = {
        "parent_only": set(),
        "address_only": {"shared_registered_address"},
        "industry_only": {"industry_sic_subclass", "industry_sic_division"},
        "postal_only": {"postcode_area", "postcode_district", "registered_post_town"},
        "all_without_legal_form": set(per_type) - {"legal_form"},
        "all": set(per_type),
    }
    components = {}
    for name, kinds in scenarios.items():
        graph = Components(nodes)
        if name not in {"address_only", "industry_only", "postal_only"}:
            for edge in edges:
                graph.join(edge["source"], edge["target"])
        for gid, group in groups.items():
            if group["kind"] in kinds:
                for node in members[gid][1:]:
                    graph.join(members[gid][0], node)
        components[name] = graph.summary(research)
    type_records = []
    for kind, gids in sorted(per_type.items()):
        company_set = {node for gid in gids for node in members[gid]}
        sizes = [len(members[gid]) for gid in gids]
        largest_id = max(gids, key=lambda gid: len(members[gid]))
        type_records.append(
            {
                "kind": kind,
                "groups": len(gids),
                "memberships": sum(sizes),
                "research_companies": len(company_set & research),
                "largest_group": max(sizes),
                "largest_label": groups[largest_id]["label"],
                **distribution(sizes),
            }
        )
    for r in labels.values():
        role, company = r["role"], r["company_id"]
        by_role[role]["graph_has_any_membership_or_parent"] += bool(
            degrees[company] + ordinary_degree[company]
        )
        by_role[role]["graph_has_parent_edge"] += ordinary_degree[company] > 0
        for kind in per_type:
            by_role[role]["hyperedge:" + kind] += kind in node_types[company]
    result["graph"] = {
        "ordinary_edges": len(edges),
        "relations": Counter(r["relation"] for r in edges),
        "relationship_registration_status": Counter(r["registration_status"] for r in edges),
        "ordinary_research_companies": sum(ordinary_degree[c] > 0 for c in research),
        "isolated_research_companies": sum(degrees[c] + ordinary_degree[c] == 0 for c in research),
        "membership_degree": distribution([degrees[c] for c in research]),
        "components": components,
        "types": type_records,
        "membership_checks": membership_checks,
        "historical_eligible_edges": sum(
            r["historical_prediction_eligible"] == "True" for r in edges
        ),
        "historical_eligible_groups": sum(
            r["historical_prediction_eligible"] == "True" for r in groups.values()
        ),
        "name_sources": Counter(nodes[c]["name_source"] for c in research),
        "current_status": Counter(nodes[c]["snapshot_company_status"] for c in research),
    }
    write_csv(out / "hyperedge-statistics.csv", type_records)
    write_csv(
        out / "role-coverage.csv",
        [{"role": role, **counts} for role, counts in sorted(by_role.items())],
    )
    write_csv(
        out / "largest-hyperedges.csv",
        [
            {**groups[gid]}
            for gid in sorted(groups, key=lambda gid: len(members[gid]), reverse=True)[:50]
        ],
    )
    address_groups = [gid for gid in groups if groups[gid]["kind"] == "shared_registered_address"]
    address_examples = []
    for gid in sorted(address_groups, key=lambda key: len(members[key]), reverse=True)[:20]:
        company_ids = members[gid]
        address_examples.append(
            {
                "group_id": gid,
                "members": len(company_ids),
                "address": nodes[company_ids[0]]["snapshot_registered_address"],
                "statuses": dict(
                    Counter(nodes[key]["snapshot_company_status"] for key in company_ids)
                ),
                "case_observed_firms": sum("case" in roles[key] for key in company_ids),
                "control_observed_firms": sum("control" in roles[key] for key in company_ids),
            }
        )
    (out / "largest-address-groups.json").write_text(
        json.dumps(address_examples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    raw_fields = Counter()
    raw_positive = Counter()
    raw_records = 0
    with gzip.open(src / "snapshot-raw-records.jsonl.gz", "rt") as stream:
        for line in stream:
            raw_records += 1
            row = json.loads(line)["row"]
            raw_fields.update(key for key, value in row.items() if str(value).strip())
            raw_positive.update(
                key
                for key, value in row.items()
                if key.startswith("Mortgages.") and str(value).strip().isdigit() and int(value) > 0
            )
    result["unextracted_snapshot_fields"] = {
        "records": raw_records,
        "nonblank_counts": raw_fields,
        "positive_mortgage_counts": raw_positive,
    }
    country_evidence = Counter()
    examples = []
    tag_counts = Counter()
    local_tag_counts = Counter()
    sampled = 0
    sample_failures = 0
    missing_report_reviews = []
    with gzip.open(src / "historical-basic-profiles.jsonl.gz", "rt") as stream:
        for line in stream:
            profile = json.loads(line)
            if profile["report_id"] in missing_report_ids:
                cache = Path(profile["raw_cache_path"])
                if cache.exists():
                    with gzip.open(cache, "rb") as raw:
                        inspection = original_dimension_candidates(
                            raw.read(), profile["period_end"]
                        )
                else:
                    inspection = {"status": "cache_unavailable"}
                missing_report_reviews.append(
                    {
                        "report_id": profile["report_id"],
                        "company_id": profile["company_id"],
                        "period_end": profile["period_end"],
                        "affected_samples": missing_report_ids[profile["report_id"]],
                        **inspection,
                    }
                )
            country = profile.get("facts", {}).get("country_of_incorporation")
            if country:
                country_evidence[country["value"]] += 1
                if country["value"] == "AllCountries" and len(examples) < 3:
                    examples.append(
                        {
                            "report_id": profile["report_id"],
                            "company_id": profile["company_id"],
                            "fact": country,
                        }
                    )
            # Report IDs are content-derived hashes; taking the first 600 in the
            # frozen file makes a reproducible exploratory sample, not a census.
            if sampled < 600:
                cache = Path(profile["raw_cache_path"])
                if not cache.exists():
                    sample_failures += 1
                    continue
                with gzip.open(cache, "rt", errors="replace") as raw:
                    document = raw.read()
                names = set(
                    re.findall(r"\bname\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]", document, flags=re.I)
                )
                tag_counts.update(names)
                local_tag_counts.update({name.rsplit(":", 1)[-1] for name in names})
                sampled += 1
    write_csv(
        out / "sampled-raw-report-tags.csv",
        [{"concept": tag, "reports": count} for tag, count in tag_counts.most_common()],
    )
    write_csv(
        out / "sampled-raw-report-local-tags.csv",
        [{"local_name": tag, "reports": count} for tag, count in local_tag_counts.most_common()],
    )
    result["raw_report_exploration"] = {
        "sampled_reports": sampled,
        "unavailable_cache_attempts": sample_failures,
        "method": (
            "first 600 available profiles in frozen file order; "
            "regex name-attribute census, not validated facts"
        ),
        "unique_name_attributes": len(tag_counts),
        "country_profile_counts": country_evidence,
        "aggregate_country_examples": examples,
    }
    result["missing_financial_report_review"] = {
        "reports": len(missing_report_reviews),
        "statuses": Counter(row["status"] for row in missing_report_reviews),
        "original_dimension_candidate_reports": sum(
            bool(row.get("concepts")) for row in missing_report_reviews
        ),
        "original_dimension_candidate_samples": sum(
            row["affected_samples"] for row in missing_report_reviews if row.get("concepts")
        ),
        "candidates_are_not_yet_validated_financial_values": True,
    }
    (out / "missing-financial-report-review.json").write_text(
        json.dumps(missing_report_reviews, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.financial_facts:
        source_fact_counts = Counter()
        source_fact_examples = []
        flow_lengths = defaultdict(list)
        with gzip.open(args.financial_facts, "rt") as stream:
            for line in stream:
                fact = json.loads(line)
                if fact.get("period_start"):
                    flow_lengths[fact["metric"]].append(
                        (
                            date.fromisoformat(fact["period_end"])
                            - date.fromisoformat(fact["period_start"])
                        ).days
                        + 1
                    )
                if fact["metric"] != "average_employees":
                    continue
                for flag, invalid in {
                    "negative": float(fact["value"]) < 0,
                    "nonzero_scale": fact.get("scale", "0") != "0",
                    "over_100000": float(fact["value"]) > 100000,
                }.items():
                    source_fact_counts[flag] += invalid
                    if invalid and len(source_fact_examples) < 12:
                        source_fact_examples.append({"flag": flag, **fact})
        result["financial_fact_evidence"] = {
            "path": str(args.financial_facts.resolve()),
            "sha256": hashlib.sha256(args.financial_facts.read_bytes()).hexdigest(),
            "employee_fact_flags": source_fact_counts,
            "examples": source_fact_examples,
            "flow_period_days": {key: distribution(value) for key, value in flow_lengths.items()},
        }
    with (out / "audit.json").open("w") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "output": str(out),
                "integrity": result["integrity"],
                "numeric_anomalies": len(anomalies),
                "graph_components": components,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
