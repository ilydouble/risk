"""Bounded CSV conversion rules; no generated code, expressions or network access."""

import csv
import hashlib
import io
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from risk_api.modules.data_prep.profile import numeric_value

ENGINE = "enterprise-csv-v1"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class ConversionColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    field: str = Field(min_length=1, max_length=4096)
    target: str = Field(default="", max_length=128)
    type: Literal["text", "number", "integer", "label", "ignore"]
    missing: Literal["reject", "null", "fill"] = "reject"
    fill: str | float | None = None
    values: dict[str, Literal[0, 1]] = Field(default_factory=dict, max_length=100)
    missingValues: list[str] = Field(
        default_factory=lambda: ["", "未知", "null", "none", "n/a"], max_length=30
    )

    @model_validator(mode="after")
    def allowed(self):
        if any(len(value) > 128 for value in self.missingValues):
            raise ValueError("Missing tokens exceed limit")
        if self.type == "ignore":
            if self.target:
                raise ValueError("Ignored fields must have no target")
            return self
        allowed = self.target in {
            "enterprise.id",
            "enterprise.name",
            "enterprise.community",
            "enterprise.label",
        }
        if not allowed:
            prefix, _, key = self.target.partition(".")
            if prefix not in {"features", "attributes"} or not key or "." in key:
                raise ValueError("Unsupported target")
        if self.target in {"enterprise.id", "enterprise.name", "enterprise.community"}:
            if self.type != "text":
                raise ValueError("Identity, name and community must remain text")
        if (self.type == "label") != (self.target == "enterprise.label"):
            raise ValueError("Labels require the explicit label target and type")
        if self.type == "label" and not self.values:
            raise ValueError("Label semantics require an explicit source-value map")
        if self.target == "enterprise.id" and self.missing != "reject":
            raise ValueError("Missing enterprise identity must be rejected")
        if self.missing == "fill" and self.fill is None:
            raise ValueError("Explicit fill value required")
        if isinstance(self.fill, str) and len(self.fill) > 4096:
            raise ValueError("Fill value exceeds limit")
        return self


class ConversionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[ConversionColumn] = Field(min_length=1, max_length=100)
    deduplicate: Literal["exact", "reject"] = "reject"
    labelMeaning: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def consistent(self):
        fields = [item.field for item in self.columns]
        targets = [item.target for item in self.columns if item.type != "ignore"]
        if len(fields) != len(set(fields)) or len(targets) != len(set(targets)):
            raise ValueError("Fields and active targets must be unique")
        if targets.count("enterprise.id") != 1:
            raise ValueError("Exactly one enterprise identity is required")
        if "enterprise.label" in targets and not self.labelMeaning.strip():
            raise ValueError("Describe label semantics; labels are not saved predictions")
        return self


def convert_value(value: str, rule: ConversionColumn) -> str | float | int | None:
    value = value.strip()
    if value.casefold() in {token.strip().casefold() for token in rule.missingValues}:
        if rule.missing == "reject":
            raise ValueError("缺失值不允许")
        if rule.missing == "null":
            return None
        value = str(rule.fill)
    if rule.type == "text":
        return value
    if rule.type == "label":
        if value not in rule.values:
            raise ValueError("标签值未在规则中定义")
        return rule.values[value]
    number = numeric_value(value)
    if number is None or not math.isfinite(float(number)):
        raise ValueError("无法解析为有限数值")
    if rule.type == "integer":
        if number != number.to_integral_value() or abs(number) > 2**53 - 1:
            raise ValueError("须为安全范围内的整数")
        return int(number)
    return float(number)


def execute(source: bytes, plan: ConversionPlan) -> tuple[list[dict], dict]:
    reader = csv.DictReader(io.StringIO(source.decode("utf-8-sig"), newline=""))
    if set(reader.fieldnames or []) != {item.field for item in plan.columns}:
        raise ValueError("规则须覆盖每个源字段；不使用的字段请显式忽略")
    output: list[dict] = []
    examples: list[dict] = []
    issues: list[dict] = []
    seen: set[tuple] = set()
    identities: set[str] = set()
    inputs = duplicates = rejected = issue_count = 0
    for line, row in enumerate(reader, 2):
        inputs += 1
        raw = tuple(row.items())
        if raw in seen and plan.deduplicate == "exact":
            duplicates += 1
            continue
        seen.add(raw)
        data: dict = {"attributes": {}, "features": {}}
        node_id = ""
        try:
            for rule in plan.columns:
                if rule.type == "ignore":
                    continue
                try:
                    value = convert_value(row[rule.field], rule)
                except ValueError as error:
                    raise ValueError(f"{rule.field}: {error}") from error
                if rule.target == "enterprise.id":
                    node_id = str(value)
                    if not node_id or len(node_id) > 512:
                        raise ValueError("企业标识为空或超过512字符")
                elif rule.target.startswith("enterprise."):
                    data[rule.target.split(".", 1)[1]] = value
                else:
                    group, key = rule.target.split(".", 1)
                    data[group][key] = value
            if node_id in identities:
                raise ValueError("企业标识重复或观测冲突；需明确聚合规则，本版不自动合并")
            identities.add(node_id)
            data.setdefault("name", node_id)
            record: dict = {
                "kind": "company",
                "snapshot": "import",
                "nodeId": node_id,
                "source": None,
                "target": None,
                "members": [],
                "data": data,
            }
            output.append(record)
            if len(examples) < 5:
                examples.append(
                    {
                        "line": line,
                        "before": {k: v[:200] for k, v in row.items()},
                        "after": {
                            **record,
                            "data": {
                                key: {
                                    k: v[:200] if isinstance(v, str) else v
                                    for k, v in value.items()
                                }
                                if isinstance(value, dict)
                                else value[:200]
                                if isinstance(value, str)
                                else value
                                for key, value in data.items()
                            },
                        },
                    }
                )
        except ValueError as error:
            rejected += 1
            issue_count += 1
            if len(issues) < 20:
                issues.append({"line": line, "message": str(error)})
    report = {
        "inputCount": inputs,
        "outputCount": len(output),
        "duplicateCount": duplicates,
        "rejectedCount": rejected,
        "issues": issues,
        "issueCount": issue_count,
        "examples": examples,
        "warnings": ["仅导入企业事实，不生成关系、训练划分或模型预测。"],
        "passed": rejected == 0 and bool(output),
    }
    # Bound persisted artifacts independently of the source file limit.
    if len(json.dumps(output, ensure_ascii=False).encode()) > 16 * 1024 * 1024:
        raise ValueError("转换产物超过16 MiB限制")
    return output, report
