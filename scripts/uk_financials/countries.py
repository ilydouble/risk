"""Normalize observed registry country spellings without guessing from company IDs."""

import re

UK = {
    "england": "england",
    "wales": "wales",
    "scotland": "scotland",
    "northernireland": "northern-ireland",
    "englandwales": "england-wales",
    "englandandwales": "england-wales",
    "englandwithintheunitedkingdom": "england",
    "unitedkingdom": "",
    "greatbritain": "",
    "uk": "",
    "gb": "",
    "gbr": "",
}
OTHER = {
    "alandislands": "AX",
    "afghanistan": "AF",
    "ireland": "IE",
    "unitedstates": "US",
    "unitedstatesofamerica": "US",
    "usa": "US",
    "france": "FR",
    "germany": "DE",
    "netherlands": "NL",
}


def normalize_country(raw):
    value = str(raw or "").strip()
    key = re.sub(r"[^a-z]", "", value.lower())
    result = {"raw_value": value, "code": "", "jurisdiction": "", "status": "unknown"}
    if key in UK:
        return {**result, "code": "GB", "jurisdiction": UK[key], "status": "normalized"}
    if key in OTHER:
        return {**result, "code": OTHER[key], "status": "normalized"}
    if not value:
        result["status"] = "missing"
    elif key in {"allcountries", "allcountriesregions", "notapplicable", "notspecified", "unknown"}:
        result["status"] = "aggregate_or_unknown"
    elif "{" in value or "}" in value or "placeofincorporation" in key:
        result["status"] = "template_placeholder"
    else:
        match = re.search(
            r"\bincorporated in\s+(england\s+(?:and|&)\s+wales|northern ireland|"
            r"united kingdom|scotland|england|wales)\b",
            value,
            flags=re.I,
        )
        if match:
            normalized = normalize_country(match[1])
            return {**normalized, "raw_value": value, "status": "normalized_explicit_description"}
    return result
