import csv
import hashlib
import io
from collections import Counter

from risk_api.errors import AppError

MAX_BYTES = 2 * 1024 * 1024
MAX_COLUMNS = 100
MAX_ROWS = 50_000
MISSING = {"", "null", "none", "n/a", "na", "未知", "无", "—", "-"}


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
    if not headers or len(headers) > MAX_COLUMNS or any(not name.strip() for name in headers):
        raise AppError(422, "DATA_PREP_HEADER_INVALID", "CSV 表头为空、列名为空或超过 100 列")
    if len(headers) != len(set(headers)):
        raise AppError(422, "DATA_PREP_HEADER_DUPLICATE", "CSV 存在重复列名")
    counts: dict[str, Counter[str]] = {name: Counter() for name in headers}
    missing = Counter[str]()
    numeric = Counter[str]()
    distinct: dict[str, set[str]] = {name: set() for name in headers}
    samples: list[dict[str, str]] = []
    row_count = 0
    duplicates = 0
    fingerprints: set[tuple[str, ...]] = set()
    for row in reader:
        row_count += 1
        if row_count > MAX_ROWS:
            raise AppError(422, "DATA_PREP_ROWS_EXCEEDED", "最多分析 50000 行，请拆分文件")
        if None in row:
            raise AppError(422, "DATA_PREP_ROW_INVALID", f"第 {row_count + 1} 行的列数超过表头")
        normalized = tuple((row[name] or "").strip() for name in headers)
        if normalized in fingerprints:
            duplicates += 1
        fingerprints.add(normalized)
        for name, value in zip(headers, normalized, strict=True):
            if value.casefold() in MISSING:
                missing[name] += 1
                continue
            counts[name][value] += 1
            distinct[name].add(value)
            try:
                float(value.replace(",", ""))
                numeric[name] += 1
            except ValueError:
                pass
        if len(samples) < 5:
            samples.append(dict(zip(headers, normalized, strict=True)))
    if row_count == 0:
        raise AppError(422, "DATA_PREP_EMPTY", "CSV 没有数据行")
    fields = []
    for name in headers:
        nonempty = row_count - missing[name]
        fields.append(
            {
                "name": name,
                "missingCount": missing[name],
                "distinctCount": len(distinct[name]),
                "numericRate": round(numeric[name] / nonempty, 3) if nonempty else 0,
                "examples": [value for value, _ in counts[name].most_common(3)],
            }
        )
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "rowCount": row_count,
        "duplicateRows": duplicates,
        "fields": fields,
        "sampleRows": samples,
    }
