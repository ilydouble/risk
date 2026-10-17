"""Fixed-vintage administrative geography; historical address verification is separate."""

import re

from uk_graph.hyperedges import POSTCODE, normalized

VINTAGE = "2026-08"
POSTCODE_SERVICE = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "ONS_Postcode_Directory_(August_2026)_(Hosted_Table)/FeatureServer/0"
)
NAME_SERVICE = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "WD26_LAD26_CTYUA26_RGN26_CTRY26_UK_LU/FeatureServer/0"
)
FIELDS = "ObjectId,pcds,dointr,doterm,ctry26cd,rgn26cd,lad26cd"


def canonical_postcode(value):
    compact = re.sub(r"\s+", "", normalized(value or ""))
    if compact == "GIR0AA" or POSTCODE.fullmatch(compact):
        return compact[:-3] + " " + compact[-3:]
    return ""


def lifecycle_compatible(record, observation_date):
    """Directory lifecycle can reject a mapping, but cannot prove an address was used."""
    month = int(observation_date[:7].replace("-", ""))
    introduced, terminated = record.get("dointr"), record.get("doterm")
    return bool(introduced) and introduced <= month and (not terminated or terminated >= month)


def administrative_facts(record, names):
    if not record:
        return []
    facts = []
    for field, kind, prefix in (
        ("lad26cd", "admin_local_authority", "行政地方当局"),
        ("rgn26cd", "admin_region", "英格兰大区"),
    ):
        code = record.get(field, "")
        # Non-English regions use sentinel codes, not region classifications.
        if code not in names or "999999" in code:
            continue
        facts.append({"kind": kind, "value": code, "label": f"{prefix}：{names[code]} ({code})"})
    return facts


def crossed_facts(industry, geography):
    """Each declared industry intersects each available administrative dimension."""
    for left in industry:
        if left["kind"] not in {"industry_sic_division", "industry_sic_subclass"}:
            continue
        for right in geography:
            yield {
                "kind": left["kind"] + "_x_" + right["kind"],
                "value": left["value"] + "|" + right["value"],
                "label": left["label"] + " × " + right["label"],
                "components": [left, right],
            }
