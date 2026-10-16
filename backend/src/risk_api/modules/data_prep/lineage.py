"""Reconstruct verified row lineage from immutable source bytes and frozen conversion rules."""

import csv
import io

from risk_api.modules.data_prep.conversion import ConversionPlan, convert_record, convert_value

MAX_VALUE = 4096
MAX_DUPLICATES = 100


def trace_company(source: bytes, plan: ConversionPlan, node: str, data: dict) -> dict:
    identity = next(rule for rule in plan.columns if rule.target == "enterprise.id")
    reader = csv.reader(io.StringIO(source.decode("utf-8-sig"), newline=""))
    header = next(reader, [])
    if set(header) != {rule.field for rule in plan.columns}:
        raise ValueError("Source header differs from frozen rules")
    previous_line = reader.line_num
    primary: dict | None = None
    duplicate_lines: list[int] = []
    duplicate_count = 0
    result: dict = {}
    ordinal = 0
    for values in reader:
        line = previous_line + 1
        previous_line = reader.line_num
        if not values:
            continue
        ordinal += 1
        row = dict(zip(header, values, strict=True))
        try:
            row_id = convert_value(row[identity.field], identity)
        except ValueError:
            continue
        if row_id != node:
            continue
        if primary is not None:
            if plan.deduplicate != "exact" or row != primary:
                raise ValueError("Source identity is ambiguous")
            duplicate_count += 1
            if len(duplicate_lines) < MAX_DUPLICATES:
                duplicate_lines.append(line)
            continue
        if convert_record(row, plan)["data"] != data:
            raise ValueError("Stored record differs from frozen conversion")
        primary = row
        result = {"sourceRow": ordinal, "sourceLine": line, "sourceEndLine": reader.line_num}
    if primary is None:
        raise ValueError("Source row unavailable")
    fields = []
    for rule in plan.columns:
        value = None if rule.type == "ignore" else convert_value(primary[rule.field], rule)
        fields.append(
            {
                "rule": rule.model_dump(),
                "originalValue": primary[rule.field][:MAX_VALUE],
                "originalTruncated": len(primary[rule.field]) > MAX_VALUE,
                "convertedValue": value[:MAX_VALUE] if isinstance(value, str) else value,
                "convertedTruncated": isinstance(value, str) and len(value) > MAX_VALUE,
                "ignored": rule.type == "ignore",
            }
        )
    return {
        **result,
        "duplicateLines": duplicate_lines,
        "duplicateCount": duplicate_count,
        "duplicatesTruncated": duplicate_count > len(duplicate_lines),
        "fields": fields,
    }
