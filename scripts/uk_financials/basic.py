"""Extract dated corporate attributes without substituting third-party contact details."""

import hashlib
import io
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from uk_financials.countries import normalize_country

NAMESPACES = (
    "http://xbrl.frc.org.uk/",
    "https://xbrl.frc.org.uk/",
    "http://www.xbrl.org/uk/",
    "http://www.companieshouse.gov.uk/ef/",
    "http://xbrl.ifrs.org/",
    "https://xbrl.ifrs.org/",
)
ALIASES = {
    "EntityCurrentLegalOrRegisteredName": "registered_name",
    "EntityName": "registered_name",
    "LegalFormEntity": "legal_form",
    "EntityLegalForm": "legal_form",
    "LegalFormOfEntity": "legal_form",
    "CountryFormationOrIncorporation": "country_of_incorporation",
    "CountryOfIncorporation": "country_of_incorporation",
    "EntityDormantTruefalse": "dormant",
    "EntityDormant": "dormant",
    "DateOfIncorporation": "incorporation_date",
    "EntityDateOfIncorporation": "incorporation_date",
    "EntityIncorporationDate": "incorporation_date",
    "IncorporationDate": "incorporation_date",
    "UKSIC2007": "sic2007",
    "UKSIC2007Code": "sic2007",
    "UKSic2007": "sic2007",
    "AddressLine1": "registered_office_address_line1",
    "AddressLine2": "registered_office_address_line2",
    "AddressLine3": "registered_office_address_line3",
    "PrincipalLocation-CityOrTown": "registered_office_town",
    "CountyRegion": "registered_office_county",
    "PostalCodeZip": "registered_office_postcode",
    "Country": "registered_office_country",
}
FIELDS = tuple(dict.fromkeys(ALIASES.values()))


def parser_signature():
    paths = [Path(__file__), Path(__file__).with_name("countries.py")]
    return hashlib.sha256(b"\n".join(path.read_bytes() for path in paths)).hexdigest()


def local(value):
    return str(value).rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def qualified(node, value):
    value = value or ""
    if value.startswith("{"):
        namespace, name = value[1:].split("}", 1)
    elif ":" in value:
        prefix, name = value.split(":", 1)
        namespace = node.nsmap.get(prefix, "")
    else:
        namespace, name = node.nsmap.get(None, ""), value
    return namespace, name


def text(node):
    return " ".join("".join(node.itertext()).split())


def identity(value):
    value = re.sub(r"\s", "", value).upper()
    return value.zfill(8) if value.isdigit() and len(value) <= 8 else value


def boolean_value(node):
    value = text(node).lower()
    form = node.get("format", "")
    if form:
        namespace, transform = qualified(node, form)
        if not namespace.startswith("http://www.xbrl.org/inlineXBRL/transformation/"):
            return None
        if transform in ("booleantrue", "fixed-true"):
            return True
        if transform in ("booleanfalse", "fixed-false"):
            return False
        if transform not in ("booltruefalse", "booleantruefalse"):
            return None
    return {"true": True, "1": True, "false": False, "0": False}.get(value)


def date_value(node):
    value, form = text(node), node.get("format", "")
    if form:
        namespace, transform = qualified(node, form)
        if not namespace.startswith("http://www.xbrl.org/inlineXBRL/transformation/"):
            return None
        formats = {
            "datedaymonthyear": "%d/%m/%Y",
            "date-day-month-year": "%d/%m/%Y",
            "dateyearmonthday": "%Y-%m-%d",
            "date-year-month-day": "%Y-%m-%d",
        }
        pattern = formats.get(transform)
        if not pattern:
            return None
    else:
        pattern = "%Y-%m-%d"
    try:
        return datetime.strptime(value, pattern).date().isoformat()
    except ValueError:
        return None


def parse_basic_document(raw, company_id, period_end):
    if raw.startswith(b"PK\x03\x04"):
        with ZipFile(io.BytesIO(raw)) as zipped:
            members = [
                m
                for m in zipped.infolist()
                if m.filename.lower().endswith((".html", ".xhtml", ".xml"))
            ]
            if len(members) != 1 or members[0].file_size > 50 * 1024 * 1024:
                raise ValueError("Multiple or oversized nested profile documents")
            raw = zipped.read(members[0])
    if b"<!ENTITY" in raw.upper():
        raise ValueError("Unsupported entity declarations")
    root = etree.fromstring(
        raw, etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
    )
    if root is None:
        raise ValueError("Profile is not XML/iXBRL")
    contexts, identifiers = {}, set()
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if local(node.tag) == "context":
            descendants = list(node.iter())
            end = next((text(n) for n in descendants if local(n.tag) in ("instant", "endDate")), "")
            if end != period_end:
                continue
            entity_ids = [identity(text(n)) for n in descendants if local(n.tag) == "identifier"]
            if any(
                re.fullmatch(r"(?:[0-9]{8}|[A-Z]{2}[0-9]{6})", value) and value != company_id
                for value in entity_ids
            ):
                continue
            dimensions = []
            for child in descendants:
                if local(child.tag) in ("explicitMember", "typedMember"):
                    dimensions.append(
                        {
                            "axis": child.get("dimension", ""),
                            "axis_namespace": qualified(child, child.get("dimension", ""))[0],
                            "member": text(child),
                            "member_namespace": qualified(child, text(child))[0],
                            "typed": local(child.tag) == "typedMember",
                        }
                    )
            contexts[node.get("id")] = {
                "end": end,
                "start": next((text(n) for n in descendants if local(n.tag) == "startDate"), ""),
                "dimensions": dimensions,
            }
        namespace, name = qualified(node, node.get("name", str(node.tag)))
        if namespace.startswith(NAMESPACES) and name in (
            "UKCompaniesHouseRegisteredNumber",
            "CompaniesHouseRegisteredNumber",
        ):
            identifiers.add(identity(text(node)))
    if identifiers and identifiers != {company_id}:
        raise ValueError("Corporate profile identity disagrees with company number")
    candidates = defaultdict(list)
    country_normalizations = []
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        namespace, concept = qualified(node, node.get("name", str(node.tag)))
        field = ALIASES.get(concept)
        if not field or not namespace.startswith(NAMESPACES):
            continue
        if node.get("name") and local(node.tag).lower() != "nonnumeric":
            continue
        if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1"):
            continue
        context = contexts.get(node.get("contextRef"))
        if not context:
            continue
        members, registered_office, accepted = {}, False, True
        for dimension in context["dimensions"]:
            axis, member = local(dimension["axis"]), local(dimension["member"])
            if dimension["typed"] or not dimension["axis_namespace"].startswith(NAMESPACES):
                accepted = False
                break
            if (axis, member) == ("GroupCompanyDataDimension", "Company"):
                continue
            if field == "legal_form" and axis == "LegalFormEntityDimension":
                members[field] = member
            elif (
                field in ("country_of_incorporation", "registered_office_country")
                and axis == "CountriesRegionsDimension"
            ):
                members[field] = member
            elif field.startswith("registered_office_") and (axis, member) == (
                "EntityContactTypeDimension",
                "RegisteredOffice",
            ):
                registered_office = True
            else:
                accepted = False
                break
        if not accepted or (field.startswith("registered_office_") and not registered_office):
            continue
        value = members.get(field, text(node))
        if field == "dormant":
            value = boolean_value(node)
        elif field == "incorporation_date":
            value = date_value(node)
            if value and value > period_end:
                value = None
        elif field == "sic2007":
            value = value if re.fullmatch(r"[0-9]{5}", value) else None
        if value is None or value == "":
            continue
        fact = {
            "field": field,
            "value": value,
            "concept": node.get("name", str(node.tag)),
            "namespace": namespace,
            "context_id": node.get("contextRef"),
            "period_start": context["start"],
            "period_end": context["end"],
            "source_text": text(node),
            "format": node.get("format", ""),
            "dimensions": context["dimensions"],
        }
        if field in {"country_of_incorporation", "registered_office_country"}:
            normalized = normalize_country(value)
            fact.update(
                raw_value=value,
                value=normalized["code"],
                jurisdiction=normalized["jurisdiction"],
                normalization_status=normalized["status"],
            )
            country_normalizations.append({"field": field, **normalized, "source_fact": fact})
            if not normalized["code"]:
                continue
        candidates[field].append(fact)
    selected, conflicts = {}, []
    for field, facts in candidates.items():
        variants = {
            (str(f["value"]), f["period_start"] if field == "dormant" else "") for f in facts
        }
        if len(variants) == 1:
            selected[field] = facts[0]
        else:
            conflicts.append(field)
    return {
        "values": {field: fact["value"] for field, fact in selected.items()},
        "facts": selected,
        "conflicts": sorted(conflicts),
        "identity_verified": company_id in identifiers,
        "country_normalizations": country_normalizations,
    }


def snapshot_date(value):
    if not value.strip():
        return ""
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()


def age_days(observation, incorporation):
    if not incorporation or incorporation > observation:
        return ""
    return (date.fromisoformat(observation) - date.fromisoformat(incorporation)).days
