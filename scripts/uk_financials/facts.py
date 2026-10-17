"""Extract selected XBRL facts without guessing missing amounts or mixing contexts."""

import hashlib
import io
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from uk_financials.quality import validate_facts

NAMESPACES = (
    "http://xbrl.frc.org.uk/",
    "https://xbrl.frc.org.uk/",
    "http://www.xbrl.org/uk/",
    "http://www.companieshouse.gov.uk/ef/",
    "http://xbrl.ifrs.org/",
    "https://xbrl.ifrs.org/",
)


def parser_signature():
    paths = [Path(__file__), Path(__file__).with_name("quality.py")]
    return hashlib.sha256(b"\n".join(path.read_bytes() for path in paths)).hexdigest()


def qualified_namespace(node, value):
    if value.startswith("{"):
        return value[1:].split("}", 1)[0]
    return node.nsmap.get(value.split(":", 1)[0], "") if ":" in value else ""


ALIASES = {
    "assets": ("Assets", "TotalAssets"),
    "fixed_assets": ("FixedAssets", "NoncurrentAssets", "AssetsNoncurrent"),
    "current_assets": ("CurrentAssets", "AssetsCurrent"),
    "current_liabilities": (
        "CreditorsDueWithinOneYear",
        "CreditorsDueWithinOneYearTotalCurrentLiabilities",
        "CurrentLiabilities",
        "LiabilitiesCurrent",
    ),
    "noncurrent_liabilities": (
        "CreditorsDueAfterOneYear",
        "CreditorsDueAfterOneYearTotalNoncurrentLiabilities",
        "NoncurrentLiabilities",
        "LiabilitiesNoncurrent",
    ),
    "net_current_assets": ("NetCurrentAssetsLiabilities",),
    "total_assets_less_current_liabilities": ("TotalAssetsLessCurrentLiabilities",),
    "cash": ("CashBankOnHand", "CashBankInHand", "CashAndCashEquivalents", "CashCashEquivalents"),
    "stocks": ("Stocks", "StocksInventory", "Inventories", "TotalInventories"),
    "debtors": ("Debtors", "TradeOtherReceivablesCurrent", "TradeAndOtherCurrentReceivables"),
    "net_assets": ("NetAssetsLiabilities", "NetAssetsLiabilitiesIncludingPensionAssetLiability"),
    "equity": ("Equity", "ShareholderFunds", "CapitalReserves"),
    "revenue": ("TurnoverRevenue", "Turnover", "Revenue"),
    "profit_loss": ("ProfitLoss", "ProfitLossForPeriod", "ProfitLossOnOrdinaryActivitiesAfterTax"),
    "operating_profit_loss": ("OperatingProfitLoss",),
    "profit_before_tax": ("ProfitLossOnOrdinaryActivitiesBeforeTax", "ProfitLossBeforeTax"),
    "average_employees": ("AverageNumberEmployeesDuringPeriod", "AverageNumberEmployees"),
}
ALIAS_METRICS = {alias: metric for metric, aliases in ALIASES.items() for alias in aliases}
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local(value):
    return str(value).rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def text(element):
    return "".join(element.itertext()).strip()


def amount(value, format_name="", scale="0", sign=""):
    value = value.strip().replace("\u00a0", "").replace(" ", "")
    if value in ("-", "—", "–") and local(format_name).lower() in ("zerodash", "numdash"):
        value = "0"
    negative_parentheses = value.startswith("(") and value.endswith(")")
    if negative_parentheses:
        value = value[1:-1]
    form = local(format_name).lower()
    if form not in {
        "",
        "numdotdecimal",
        "num-dot-decimal",
        "numcommadot",
        "numdotcomma",
        "numcommadecimal",
        "num-comma-decimal",
        "zerodash",
        "numdash",
    }:
        return None
    if form in ("numcommadecimal", "num-comma-decimal", "numdotcomma"):
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", "")
    try:
        number = Decimal(value) * (Decimal(10) ** int(scale))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    if sign == "-" or negative_parentheses:
        number = -abs(number)
    return str(number.normalize())


def parse_document(raw, company_id, period_end):
    if raw.startswith(b"PK\x03\x04"):
        with ZipFile(io.BytesIO(raw)) as zipped:
            names = [
                i
                for i in zipped.infolist()
                if i.filename.lower().endswith((".html", ".xhtml", ".xml"))
            ]
            if len(names) != 1 or names[0].file_size > 50 * 1024 * 1024:
                raise ValueError("Nested filing requires multiple-document review")
            raw = zipped.read(names[0])
    if b"<!ENTITY" in raw.upper():
        raise ValueError("Document declares unsupported entities")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True)
    root = etree.fromstring(raw, parser)
    if root is None:
        raise ValueError("Financial document is not parseable XML/iXBRL")
    contexts, units = {}, {}
    identifiers = set()
    for node in root.iter():
        name = local(node.tag).lower()
        if name == "context":
            children = list(node.iter())
            instant = next((text(x) for x in children if local(x.tag) == "instant"), None)
            end = next((text(x) for x in children if local(x.tag) == "endDate"), instant)
            start = next((text(x) for x in children if local(x.tag) == "startDate"), None)
            dimensions = [
                {
                    "axis": local(x.get("dimension", "")),
                    "member": local(text(x)),
                    "axis_namespace": qualified_namespace(x, x.get("dimension", "")),
                    "member_namespace": qualified_namespace(x, text(x)),
                    "typed": local(x.tag) == "typedMember",
                }
                for x in children
                if local(x.tag) in ("explicitMember", "typedMember")
            ]
            contexts[node.get("id")] = {
                "end": end,
                "start": start,
                "dimensions": dimensions,
                "instant": instant,
                "entity_identifiers": [
                    re.sub(r"\s", "", text(x)).upper()
                    for x in children
                    if local(x.tag) == "identifier"
                ],
            }
        if name == "unit":
            measures = [text(x) for x in node.iter() if local(x.tag) == "measure"]
            units[node.get("id")] = measures
        concept = local(node.get("name", node.tag))
        if concept in ("UKCompaniesHouseRegisteredNumber", "CompaniesHouseRegisteredNumber"):
            value = re.sub(r"\s", "", text(node)).upper()
            if value.isdigit():
                value = value.zfill(8)
            identifiers.add(value)
    if identifiers and company_id not in identifiers:
        raise ValueError("XBRL company identity disagrees with the official filename")
    observations = []
    for node in root.iter():
        concept = local(node.get("name", node.tag))
        metric = ALIAS_METRICS.get(concept)
        if (not metric and concept != "Creditors") or node.get(NIL) == "true":
            continue
        if node.get("name") and local(node.tag).lower() != "nonfraction":
            continue
        qualified = node.get("name", node.tag)
        namespace = (
            node.nsmap.get(qualified.split(":", 1)[0], "")
            if ":" in qualified and not qualified.startswith("{")
            else qualified.split("}", 1)[0].lstrip("{")
        )
        if not namespace.startswith(
            (
                "http://xbrl.frc.org.uk/",
                "https://xbrl.frc.org.uk/",
                "http://www.xbrl.org/uk/",
                "http://www.companieshouse.gov.uk/ef/",
                "http://xbrl.ifrs.org/",
                "https://xbrl.ifrs.org/",
            )
        ):
            continue
        reference = node.get("contextRef")
        context = contexts.get(reference)
        if not context or context["end"] != period_end:
            continue
        if any(
            re.fullmatch(r"(?:[0-9]{1,8}|[A-Z]{2}[0-9]{6})", value)
            and (value.zfill(8) if value.isdigit() else value) != company_id
            for value in context["entity_identifiers"]
        ):
            continue
        dimensions = []
        invalid_dimension = False
        for dimension in context["dimensions"]:
            if (
                dimension["typed"]
                or not dimension["axis_namespace"].startswith(NAMESPACES)
                or not dimension["member_namespace"].startswith(NAMESPACES)
            ):
                invalid_dimension = True
                break
            if (dimension["axis"], dimension["member"]) == (
                "OriginalRevisedDataDimension",
                "Original",
            ):
                continue
            dimensions.append((dimension["axis"], dimension["member"]))
        if invalid_dimension:
            continue
        if concept == "Creditors":
            kinds = set()
            for axis, member in dimensions:
                if (axis, member) in {
                    ("MaturitiesOrExpirationPeriodsDimension", "WithinOneYear"),
                    (
                        "FinancialInstrumentCurrentNon-currentDimension",
                        "CurrentFinancialInstruments",
                    ),
                }:
                    kinds.add("current_liabilities")
                elif (axis, member) in {
                    ("MaturitiesOrExpirationPeriodsDimension", "AfterOneYear"),
                    (
                        "FinancialInstrumentCurrentNon-currentDimension",
                        "Non-currentFinancialInstruments",
                    ),
                }:
                    kinds.add("noncurrent_liabilities")
                else:
                    kinds.add("unsupported_dimension")
            if len(kinds) != 1 or "unsupported_dimension" in kinds:
                continue
            metric = kinds.pop()
        elif dimensions:
            continue  # Segment/group/member totals cannot be silently substituted for entity facts.
        flow = metric in {
            "revenue",
            "profit_loss",
            "operating_profit_loss",
            "profit_before_tax",
            "average_employees",
        }
        if (flow and not context["start"]) or (not flow and not context["instant"]):
            continue
        unit = units.get(node.get("unitRef"), [])
        if len(unit) != 1:
            continue
        currency = local(unit[0])
        if metric == "average_employees":
            if currency != "pure":
                continue
        elif not re.fullmatch(r"[A-Z]{3}", currency):
            continue
        value = amount(
            text(node), node.get("format", ""), node.get("scale", "0"), node.get("sign", "")
        )
        if value is not None:
            observations.append(
                {
                    "metric": metric,
                    "value": value,
                    "unit": currency,
                    "concept": node.get("name", node.tag),
                    "context_id": reference,
                    "period_start": context["start"],
                    "period_end": context["end"],
                    "decimals": node.get("decimals"),
                    "source_text": text(node),
                    "format": node.get("format", ""),
                    "scale": node.get("scale", "0"),
                    "sign": node.get("sign", ""),
                    "namespace": namespace,
                    "dimensions": context["dimensions"],
                }
            )
    selected, conflicts = {}, []
    for metric in ALIASES:
        candidates = [fact for fact in observations if fact["metric"] == metric]
        variants = {(f["value"], f["unit"], f["period_start"]) for f in candidates}
        if len(variants) == 1:
            selected[metric] = candidates[0]
        elif variants:
            conflicts.append(metric)
    currencies = {
        fact["unit"] for metric, fact in selected.items() if metric != "average_employees"
    }
    if len(currencies) > 1:
        conflicts.extend(metric for metric in selected if metric != "average_employees")
        selected = {key: value for key, value in selected.items() if key == "average_employees"}
    accepted, issues = validate_facts(selected, company_id)
    return {
        "facts": accepted,
        "source_facts": selected,
        "quality_issues": issues,
        "conflicting_metrics": sorted(set(conflicts)),
        "identity_verified_in_document": company_id in identifiers,
        "document_identity_fields": sorted(identifiers),
        "matching_context_facts": len(observations),
    }
