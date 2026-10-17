"""UK observation identity, forward horizon and feature provenance invariants."""

import json
from pathlib import Path

POLICY = json.loads(Path(__file__).with_name("feature-policy.json").read_text())
YEARS = {"train": {"2019", "2020"}, "valid": {"2022"}, "test": {"2024"}}
RELATIONS = ["IS_DIRECTLY_CONSOLIDATED_BY", "IS_ULTIMATELY_CONSOLIDATED_BY"]
HYPEREDGES = [
    "admin_local_authority",
    "admin_region",
    "common_direct_parent",
    "common_ultimate_parent",
    "industry_sic_division",
    "industry_sic_division_x_admin_local_authority",
    "industry_sic_division_x_admin_region",
    "industry_sic_subclass",
    "industry_sic_subclass_x_admin_local_authority",
    "industry_sic_subclass_x_admin_region",
    "legal_form",
    "postcode_area",
    "postcode_district",
    "registered_post_town",
    "shared_registered_address",
]
TARGET = "Primary formal insolvency observed in the next 12 months (matched research cohort)"


def feature_names(policy):
    if (
        policy.get("fitSplit") != "train"
        or policy.get("categoricalEncoding") != "train-vocabulary-one-hot-with-unknown"
    ):
        raise ValueError("UK preprocessing must use training data only")
    if policy["numeric"] != POLICY["numericFeatureAllowlist"]:
        raise ValueError("UK numeric feature allowlist mismatch")
    if set(policy["categories"]) != set(POLICY["categoricalFeatureAllowlist"]):
        raise ValueError("UK categorical feature allowlist mismatch")
    names = list(policy["numeric"])
    for name, values in policy["categories"].items():
        if values != sorted(set(values)) or any(
            not isinstance(v, str) or not v or v == "__unknown__" for v in values
        ):
            raise ValueError("Invalid training category vocabulary")
        names += [f"cat:{name}:{value}" for value in values] + [f"cat:{name}:__unknown__"]
    if policy["signedLog1p"] != [n for n in policy["numeric"] if not n.endswith("_missing")]:
        raise ValueError("UK continuous feature transform mismatch")
    return names


def check(snapshots, policy):
    expected = feature_names(policy)
    seen_companies, seen_pairs = set(), set()
    previous_end = ""
    for split, snapshot in snapshots.items():
        if (
            snapshot.feature_names != expected
            or snapshot.relation_names != RELATIONS
            or snapshot.hyperedge_types != HYPEREDGES
            or snapshot.target_description != TARGET
        ):
            raise ValueError("Unsupported UK research schema")
        if snapshot.events or any(n.kind != "company" for n in snapshot.nodes):
            raise ValueError("UK research has observation nodes only and no event inputs")
        companies, pairs, months = set(), {}, {}
        for node in snapshot.nodes:
            p = node.properties
            company, month = p["company_id"], p["observation_month"]
            if node.id != p["sample_id"] or not company or month[:4] not in YEARS[split]:
                raise ValueError("Invalid UK observation identity or split year")
            year, number = map(int, month.split("-"))
            if (
                not 1 <= number <= 12
                or month != f"{year:04d}-{number:02d}"
                or p["followup_end_month"] != f"{year + 1:04d}-{number:02d}"
                or p["prediction_horizon_months"] != 12
            ):
                raise ValueError("Invalid UK 12-month horizon")
            companies.add(company)
            months[node.id] = month
            pairs.setdefault(p["pair_id"], []).append(node)
        if companies & seen_companies or set(pairs) & seen_pairs:
            raise ValueError("UK company/pair crosses train/validation/test")
        if previous_end and previous_end >= min(months.values()):
            raise ValueError("UK prediction horizon overlaps the next split")
        previous_end = max(n.properties["followup_end_month"] for n in snapshot.nodes)
        for pair in pairs.values():
            if (
                len(pair) != 2
                or {n.label for n in pair} != {0, 1}
                or len({n.properties["company_id"] for n in pair}) != 2
                or len({months[n.id] for n in pair}) != 1
            ):
                raise ValueError("UK matched case/control pair is incomplete")
        for edge in snapshot.edges:
            if months[edge.source] != months[edge.target] or edge.weight != 1:
                raise ValueError("UK edges must be unit-weight within one observation month")
            if edge.existence_confidence is not None or edge.strength is not None:
                raise ValueError("UK source does not supply calibrated edge confidence/strength")
        for group in snapshot.hyperedges:
            if len(group.members) < 2 or len({months[n] for n in group.members}) != 1:
                raise ValueError("UK hyperedge mixes observation months or has one member")
        seen_companies.update(companies)
        seen_pairs.update(pairs)
