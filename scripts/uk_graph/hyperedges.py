"""Source-backed attribute and common-parent hyperedges, without pairwise expansion."""

import re
import unicodedata

from uk_graph.gleif import stable_id

SOURCE_DATE = "2026-09-30"
EXCLUDED_SIC = {"74990", "99999"}
POSTCODE = re.compile(
    r"^(?P<outward>[A-PR-UWYZ][A-HK-Y]?[0-9][A-Z0-9]?)(?P<inward>[0-9][ABD-HJLNP-UW-Z]{2})$"
)
KINDS = {
    "industry_sic_division": ("attribute", "industry", "2", "MEMBER_OF_INDUSTRY_SIC_DIVISION"),
    "industry_sic_subclass": ("attribute", "industry", "5", "MEMBER_OF_INDUSTRY_SIC_SUBCLASS"),
    "postcode_area": ("attribute", "postal_geography", "area", "MEMBER_OF_POSTCODE_AREA"),
    "postcode_district": (
        "attribute",
        "postal_geography",
        "district",
        "MEMBER_OF_POSTCODE_DISTRICT",
    ),
    "registered_post_town": (
        "attribute",
        "postal_geography",
        "town",
        "MEMBER_OF_REGISTERED_POST_TOWN",
    ),
    "legal_form": ("attribute", "legal_form", "category", "MEMBER_OF_LEGAL_FORM"),
    "common_direct_parent": (
        "relational",
        "accounting_parent",
        "direct",
        "MEMBER_OF_COMMON_DIRECT_PARENT",
    ),
    "common_ultimate_parent": (
        "relational",
        "accounting_parent",
        "ultimate",
        "MEMBER_OF_COMMON_ULTIMATE_PARENT",
    ),
    "shared_registered_address": (
        "attribute",
        "postal_geography",
        "address",
        "MEMBER_OF_REGISTERED_ADDRESS_GROUP",
    ),
}


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).upper().split())


def postal_units(value):
    match = POSTCODE.fullmatch(re.sub(r"\s+", "", normalized(value)))
    if not match:
        return None
    outward = match["outward"]
    return re.match(r"[A-Z]+", outward)[0], outward


def group_id(kind, value, date=SOURCE_DATE):
    return kind.upper() + ":" + stable_id([date, value])


def snapshot_facts(row, sic_codes):
    """Multiple declared SIC codes may share a division: one membership with all evidence."""
    facts = {}

    def add(kind, key, label, fields, values, parent=""):
        item = facts.setdefault(
            (kind, key),
            {
                "kind": kind,
                "value": key,
                "label": label,
                "source_fields": [],
                "source_values": [],
                "parent_group_id": parent,
            },
        )
        for field, value in zip(fields, values, strict=True):
            if field not in item["source_fields"]:
                item["source_fields"].append(field)
                item["source_values"].append(value)

    for number in range(1, 5):
        field = f"SICCode.SicText_{number}"
        value = row.get(field, "").strip()
        match = re.match(r"^([0-9]{5})(?:\s*-|$)", value)
        code = match[1] if match else ""
        if code not in sic_codes or code in EXCLUDED_SIC:
            continue
        division = code[:2]
        add("industry_sic_division", division, "SIC 2007 两位行业：" + division, [field], [value])
        add(
            "industry_sic_subclass",
            code,
            code + " — " + sic_codes[code],
            [field],
            [value],
            group_id("industry_sic_division", division),
        )
    postcode = row.get("RegAddress.PostCode", "")
    postal = postal_units(postcode)
    if postal:
        area, district = postal
        area_id = group_id("postcode_area", area)
        add("postcode_area", area, "邮区：" + area, ["RegAddress.PostCode"], [postcode])
        add(
            "postcode_district",
            district,
            "邮政分区：" + district,
            ["RegAddress.PostCode"],
            [postcode],
            area_id,
        )
        town_raw = row.get("RegAddress.PostTown", "")
        town = normalized(town_raw)
        if town and town not in {"UNKNOWN", "N/A", "NA", "NONE", "NULL", "NOT KNOWN", "-"}:
            add(
                "registered_post_town",
                area + "|" + town,
                "登记邮政城镇：" + town + "（" + area + "）",
                ["RegAddress.PostTown", "RegAddress.PostCode"],
                [town_raw, postcode],
                area_id,
            )
    legal_raw = row.get("CompanyCategory", "")
    legal = normalized(legal_raw)
    if legal and legal not in {"UNKNOWN", "N/A", "NA", "NONE", "NULL", "-"}:
        add("legal_form", legal, "法律形式：" + legal_raw, ["CompanyCategory"], [legal_raw])
    return list(facts.values())


def common_parent_facts(edges):
    for number, row in enumerate(edges, 2):
        kind = {
            "IS_DIRECTLY_CONSOLIDATED_BY": "common_direct_parent",
            "IS_ULTIMATELY_CONSOLIDATED_BY": "common_ultimate_parent",
        }.get(row["relation"])
        if kind:
            yield {
                "node_id": row["source"],
                "kind": kind,
                "value": row["target"],
                "label": (
                    "共同直接并表母公司："
                    if kind == "common_direct_parent"
                    else "共同最终并表母公司："
                )
                + row["target"],
                "source_fields": ["source", "target", "relation"],
                "source_values": [row["source"], row["target"], row["relation"]],
                "source_record_number": number,
                "source_record_id": row["id"],
                "source_row_sha256": stable_id(row),
                "parent_group_id": "",
                "source_date": row["source_publish_date"],
                "source_sha256": row["source_archive_sha256"],
            }
