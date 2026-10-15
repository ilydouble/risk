import csv
import hashlib
import io
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from statistics import quantiles

from risk_api.errors import AppError

MAX_BYTES = 2 * 1024 * 1024
MAX_COLUMNS = 100
MAX_ROWS = 50_000
MISSING = {"", "null", "none", "n/a", "na", "未知", "无", "—", "-"}
GROUPED_NUMBER = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(?:\.\d+)?$")
DATE_PREFIX = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}(?:$|[ T])")


def numeric_value(value: str) -> Decimal | None:
    if len(value) > 64:
        return None
    if "," in value and not GROUPED_NUMBER.fullmatch(value):
        return None
    try:
        result = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None
    return result if result.is_finite() and abs(result.adjusted()) <= 100 else None


def is_date(value: str) -> bool:
    if len(value) > 40 or not DATE_PREFIX.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("/", "-"))
    except ValueError:
        return False
    return True


def decimal_text(value: Decimal) -> str:
    return format(value, ".8g")


def preview(value: str) -> str:
    return value if len(value) <= 80 else value[:80] + "…"


def numeric_summary(values: list[Decimal]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    quartiles = quantiles(ordered, n=4, method="inclusive") if len(ordered) >= 2 else None
    q1 = quartiles[0] if quartiles else ordered[0]
    q3 = quartiles[2] if quartiles else ordered[0]
    spread = q3 - q1
    outliers = 0
    if len(ordered) >= 8 and spread > 0:
        low, high = q1 - spread * Decimal("1.5"), q3 + spread * Decimal("1.5")
        outliers = sum(value < low or value > high for value in ordered)
    middle = len(ordered) // 2
    middle_value = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / Decimal(2)
    )
    return {
        "min": decimal_text(ordered[0]),
        "median": decimal_text(middle_value),
        "max": decimal_text(ordered[-1]),
        "mean": decimal_text(sum(ordered, Decimal(0)) / Decimal(len(ordered))),
        "q1": decimal_text(q1),
        "q3": decimal_text(q3),
        "outlierCount": outliers,
    }


def key_kind(name: str) -> str | None:
    lowered = name.casefold().strip()
    if lowered in {"id", "company_id", "enterprise_id", "企业编号", "企业id", "统一社会信用代码"}:
        return "entity_key"
    if lowered.endswith("_id") or lowered.endswith("编号"):
        return "relation_key"
    return None


def is_label_candidate(name: str) -> bool:
    lowered = name.casefold().strip()
    return any(
        marker in lowered
        for marker in ("label", "target", "adverse", "default", "不良", "违约", "标签")
    )


def issue(code: str, message: str, count: int, field: str | None = None) -> dict:
    return {"code": code, "message": message, "count": count, "field": field}


def inspect_csv(content: bytes) -> dict:
    if not content or len(content) > MAX_BYTES:
        raise AppError(422, "DATA_PREP_SIZE_INVALID", "CSV 文件必须小于 2 MiB 且不能为空")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise AppError(422, "DATA_PREP_ENCODING_INVALID", "请将 CSV 保存为 UTF-8 编码") from error
    try:
        dialect = csv.Sniffer().sniff(decoded[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(decoded, newline=""), dialect=dialect)
    headers = reader.fieldnames or []
    if (not headers or len(headers) > MAX_COLUMNS
            or any(not name.strip() or len(name) > 4096 for name in headers)):
        raise AppError(422, "DATA_PREP_HEADER_INVALID", "CSV 表头为空、列名为空或超过 100 列")
    if len(headers) != len(set(headers)):
        raise AppError(422, "DATA_PREP_HEADER_DUPLICATE", "CSV 存在重复列名")
    counts: dict[str, Counter[str]] = {name: Counter() for name in headers}
    missing = Counter[str]()
    numeric = Counter[str]()
    dates = Counter[str]()
    whitespace = Counter[str]()
    leading_zero = Counter[str]()
    numbers: dict[str, list[Decimal]] = {name: [] for name in headers}
    samples: list[dict[str, str]] = []
    row_count = 0
    rows_with_missing = 0
    duplicates = 0
    fingerprints: set[tuple[str, ...]] = set()
    for row in reader:
        row_count += 1
        if row_count > MAX_ROWS:
            raise AppError(422, "DATA_PREP_ROWS_EXCEEDED", "最多分析 50000 行，请拆分文件")
        if None in row:
            raise AppError(422, "DATA_PREP_ROW_INVALID", f"第 {row_count + 1} 行的列数超过表头")
        raw = tuple(row[name] or "" for name in headers)
        normalized = tuple(value.strip() for value in raw)
        if normalized in fingerprints:
            duplicates += 1
        fingerprints.add(normalized)
        row_missing = False
        for name, original, value in zip(headers, raw, normalized, strict=True):
            if original != value:
                whitespace[name] += 1
            if value.casefold() in MISSING:
                missing[name] += 1
                row_missing = True
                continue
            counts[name][value] += 1
            number = numeric_value(value)
            if number is not None:
                numeric[name] += 1
                numbers[name].append(number)
                if re.fullmatch(r"0\d+", value):
                    leading_zero[name] += 1
            if is_date(value):
                dates[name] += 1
        if row_missing:
            rows_with_missing += 1
        if len(samples) < 5:
            samples.append(
                dict(zip(headers, (preview(value) for value in normalized), strict=True))
            )
    if row_count == 0:
        raise AppError(422, "DATA_PREP_EMPTY", "CSV 没有数据行")
    fields = []
    issues = []
    candidates = []
    label_candidates = []
    if duplicates:
        issues.append(issue("DUPLICATE_ROWS", "存在完全重复的记录，需核对是否应去重。", duplicates))
    if rows_with_missing:
        issues.append(issue("ROWS_WITH_MISSING", "部分记录含缺失或占位符值。", rows_with_missing))
    for name in headers:
        nonempty = row_count - missing[name]
        distinct_count = len(counts[name])
        numeric_rate = numeric[name] / nonempty if nonempty else 0
        date_rate = dates[name] / nonempty if nonempty else 0
        kind = key_kind(name)
        if nonempty == 0:
            type_hint = "empty"
        elif kind or leading_zero[name]:
            type_hint = "identifier"
        elif numeric_rate >= 0.95:
            type_hint = "number"
        elif date_rate >= 0.95:
            type_hint = "date"
        elif 0.05 < numeric_rate < 0.95:
            type_hint = "mixed"
        elif distinct_count <= 50 and distinct_count <= max(3, nonempty * 0.5):
            type_hint = "category"
        else:
            type_hint = "text"
        summary = numeric_summary(numbers[name]) if type_hint in {"number", "mixed"} else None
        top_values = [
            {"value": preview(value), "count": count}
            for value, count in counts[name].most_common(3)
        ]
        fields.append(
            {
                "name": name,
                "missingCount": missing[name],
                "distinctCount": distinct_count,
                "numericRate": round(numeric_rate, 3),
                "dateRate": round(date_rate, 3),
                "typeHint": type_hint,
                "whitespaceCount": whitespace[name],
                "leadingZeroCount": leading_zero[name],
                "topValues": top_values,
                "numericSummary": summary,
                "examples": [item["value"] for item in top_values],
            }
        )
        if nonempty == 0:
            issues.append(issue("ALL_MISSING", "整列没有可用值。", row_count, name))
        elif missing[name] / row_count >= 0.3:
            issues.append(
                issue(
                    "HIGH_MISSING", "缺失比例至少 30%，需确认填补或剔除策略。", missing[name], name
                )
            )
        if nonempty and distinct_count == 1:
            issues.append(
                issue("CONSTANT", "非缺失值只有一种，建模信息量可能有限。", nonempty, name)
            )
        if type_hint == "mixed":
            issues.append(
                issue(
                    "MIXED_NUMERIC",
                    "数值与非数值混用，需确认单位或占位符。",
                    nonempty - numeric[name],
                    name,
                )
            )
        elif type_hint == "number" and numeric[name] < nonempty:
            issues.append(
                issue(
                    "NON_NUMERIC_VALUES",
                    "疑似数值列含无法解析的值，需核对原始取值。",
                    nonempty - numeric[name],
                    name,
                )
            )
        if date_rate >= 0.5 and date_rate < 1:
            issues.append(
                issue(
                    "MIXED_DATE",
                    "疑似日期列含无法解析的日期值，需统一格式。",
                    nonempty - dates[name],
                    name,
                )
            )
        if whitespace[name]:
            issues.append(
                issue(
                    "WHITESPACE",
                    "部分值含前后空格，当前统计按去空格后计算。",
                    whitespace[name],
                    name,
                )
            )
        if leading_zero[name]:
            issues.append(
                issue(
                    "LEADING_ZERO",
                    "含前导零，关联和导出时应始终保留为文本。",
                    leading_zero[name],
                    name,
                )
            )
        if summary and summary["outlierCount"]:
            issues.append(
                issue(
                    "POSSIBLE_OUTLIER",
                    "按四分位距发现疑似离群值，需结合业务核对。",
                    summary["outlierCount"],
                    name,
                )
            )
        if kind:
            candidates.append(
                {
                    "field": name,
                    "kind": kind,
                    "nonMissingCount": nonempty,
                    "duplicateValues": nonempty - distinct_count,
                }
            )
            if kind == "entity_key" and nonempty - distinct_count > 0:
                issues.append(
                    issue(
                        "DUPLICATE_KEY",
                        "疑似企业标识存在重复，需确认一行代表什么实体。",
                        nonempty - distinct_count,
                        name,
                    )
                )
        if is_label_candidate(name):
            value_counts = counts[name]
            minority_share = (
                min(value_counts.values()) / nonempty
                if len(value_counts) == 2 and nonempty
                else None
            )
            label_candidates.append(
                {
                    "field": name,
                    "values": top_values,
                    "missingCount": missing[name],
                    "distinctCount": distinct_count,
                    "minorityShare": round(minority_share, 3)
                    if minority_share is not None
                    else None,
                }
            )
            if minority_share is not None and minority_share < 0.1:
                issues.append(
                    issue(
                        "POSSIBLE_CLASS_IMBALANCE",
                        "疑似二分类标签类别不均衡；训练与验证时需分层核查。",
                        min(value_counts.values()),
                        name,
                    )
                )
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "rowCount": row_count,
        "rowsWithMissing": rows_with_missing,
        "duplicateRows": duplicates,
        "fields": fields,
        "issues": issues,
        "keyCandidates": candidates,
        "labelCandidates": label_candidates,
        "sampleRows": samples,
    }
