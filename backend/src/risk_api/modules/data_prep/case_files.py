"""Immutable case file container; CSV semantics remain independent of graph evidence."""

import base64
import hashlib
import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from risk_api.errors import AppError
from risk_api.modules.data_prep.conversion import ConversionPlan, execute
from risk_api.modules.data_prep.profile import inspect_csv
from risk_api.modules.modeling.enterprise_data import finite_float, reject_constant

CASE_ENGINE = "enterprise-case-v1"
MAX_GRAPH_BYTES = 64 * 1024 * 1024
MAX_CASE_BYTES = 96 * 1024 * 1024
MAX_RECORDS = 500_000


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    relation: str = Field(min_length=1, max_length=128)
    weight: float | None = Field(default=None, ge=0)


class GraphGroup(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    kind: str = Field(min_length=1, max_length=128)
    members: list[str] = Field(min_length=2, max_length=50_000)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1, max_length=512)
    kind: str = "company"


class GraphDocument(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=MAX_RECORDS)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=MAX_RECORDS)
    hyperedges: list[GraphGroup] = Field(default_factory=list, max_length=MAX_RECORDS)
    feature_names: list[str] = Field(default_factory=list, max_length=100)
    events: list[Any] = Field(default_factory=list, max_length=0)


def graph_document(content: bytes) -> GraphDocument:
    try:
        raw = json.loads(content.decode("utf-8-sig"), parse_constant=reject_constant,
                         parse_float=finite_float, object_pairs_hook=unique_keys)
        if not isinstance(raw, dict) or not any(k in raw for k in ("edges", "hyperedges")):
            raise ValueError("须包含edges或hyperedges数组")
        graph = GraphDocument.model_validate(raw)
        if len(graph.nodes) + len(graph.edges) + len(graph.hyperedges) > MAX_RECORDS:
            raise ValueError("图记录超过500000条")
        if any(node.kind != "company" for node in graph.nodes):
            raise ValueError("当前案例仅支持企业节点，不支持人物节点")
        if len({node.id for node in graph.nodes}) != len(graph.nodes):
            raise ValueError("图节点ID重复")
        if len(set(graph.feature_names)) != len(graph.feature_names):
            raise ValueError("feature_names不能重复")
        for group in graph.hyperedges:
            if len(set(group.members)) != len(group.members) or any(
                not member or len(member) > 512 for member in group.members
            ):
                raise ValueError("群组成员ID为空、重复或过长")
        return graph
    except (ValueError, UnicodeError, RecursionError, ValidationError) as error:
        message = ("图结构或字段类型无效，请检查节点id、边source/target/relation和群组kind/members"
                   if isinstance(error, ValidationError) else str(error)[:300])
        raise AppError(422, "DATA_PREP_GRAPH_INVALID", message) from error


def unique_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON包含重复键")
        result[key] = value
    return result


def unpack_source(source: bytes, profile: dict) -> list[tuple[str, bytes]]:
    if not profile.get("caseFiles"):
        return [("source.csv", source)]
    # Only containers produced here are unpacked, never a user-provided ZIP.
    raw = json.loads(source)
    if raw.get("format") != CASE_ENGINE:
        raise ValueError("案例文件容器无效")
    return [(f["filename"], base64.b64decode(f["content"], validate=True)) for f in raw["files"]]


def primary_source(source: bytes, profile: dict) -> tuple[str, bytes]:
    files = unpack_source(source, profile)
    return next((name, data) for name, data in files if name.lower().endswith(".csv"))


def build_case(files: list[tuple[str, bytes]]) -> tuple[bytes, dict]:
    if not 1 <= len(files) <= 8 or sum(len(data) for _, data in files) > MAX_CASE_BYTES:
        raise AppError(422, "DATA_PREP_SIZE_INVALID", "案例最多8个文件，总大小不超过96 MiB")
    names = [name for name, _ in files]
    if len(set(names)) != len(names) or any(
        not name or len(name) > 255 or name in {".", ".."}
        or any(char in name for char in ("/", "\\", "\x00")) for name in names
    ):
        raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件名不能重复或包含路径")
    csv_files = [(name, data) for name, data in files if name.lower().endswith(".csv")]
    if len(csv_files) != 1 or any(not name.lower().endswith((".csv", ".json")) for name in names):
        raise AppError(422, "DATA_PREP_FORMAT_UNSUPPORTED",
                       "每个案例需要一张企业属性CSV主表，可附加多个图JSON；其他表请建立独立案例")
    profile = inspect_csv(csv_files[0][1])
    if len(files) == 1:
        return csv_files[0][1], profile
    manifest = []
    for name, data in sorted(files):
        sha = hashlib.sha256(data).hexdigest()
        entry: dict = {"filename": name, "sha256": sha, "size": len(data),
                       "role": "enterprises" if name.lower().endswith(".csv") else "graph"}
        if entry["role"] == "graph":
            if not data or len(data) > MAX_GRAPH_BYTES:
                raise AppError(422, "DATA_PREP_SIZE_INVALID", "单个图JSON须在1字节至64 MiB之间")
            try:
                graph = graph_document(data)
            except AppError as error:
                raise AppError(error.status, error.code,
                               f"{name}：{error.message}") from error
            entry.update(nodeCount=len(graph.nodes), edgeCount=len(graph.edges),
                         hyperedgeCount=len(graph.hyperedges),
                         relationTypes=dict(Counter(e.relation for e in graph.edges)),
                         groupTypes=dict(Counter(g.kind for g in graph.hyperedges)))
        manifest.append(entry)
    source = json.dumps({"format": CASE_ENGINE, "files": [
        {"filename": name, "content": base64.b64encode(data).decode()}
        for name, data in sorted(files)
    ]}, ensure_ascii=False, separators=(",", ":")).encode()
    profile.update(caseFiles=manifest, primaryFilename=csv_files[0][0],
                   sha256=hashlib.sha256(source).hexdigest())
    return source, profile


def execute_case(source: bytes, profile: dict, plan: ConversionPlan) -> tuple[list[dict], dict]:
    _, csv_source = primary_source(source, profile)
    output, report = execute(csv_source, plan)
    companies = {record["nodeId"]: record["data"] for record in output}
    explicit_name = any(rule.target == "enterprise.name" for rule in plan.columns)
    counts = {"company": len(output), "edge": 0, "hyperedge": 0}
    graph_report: dict = {"referencedCount": 0, "matchedCount": 0, "missingCount": 0,
                         "missingIds": [], "conflictCount": 0, "duplicateCount": 0,
                         "files": []}
    referenced: set[str] = set()
    missing: set[str] = set()
    seen: dict[tuple, dict] = {}

    def issue(filename: str, path: str, message: str, conflict: bool = False) -> None:
        report["issueCount"] += 1
        report["rejectedCount"] += 1
        graph_report["conflictCount"] += int(conflict)
        if len(report["issues"]) < 20:
            report["issues"].append({"line": 0, "filename": filename,
                                     "path": path, "message": message})

    for filename, content in unpack_source(source, profile):
        if filename.lower().endswith(".csv"):
            continue
        graph = graph_document(content)
        sha = hashlib.sha256(content).hexdigest()
        file_refs: set[str] = set()
        for index, node in enumerate(graph.nodes):
            file_refs.add(node.id)
            if node.id not in companies:
                issue(filename, f"nodes[{index}]", f"图节点 {node.id} 不在CSV转换结果中")
                continue
            data = companies[node.id]
            raw = node.model_dump()
            comparisons: dict[str, Any] = {
                key: raw[key] for key in ("name", "community", "label") if key in raw
            }
            if not explicit_name:
                comparisons.pop("name", None)
            features = raw.get("features")
            if isinstance(features, list):
                if len(features) != len(graph.feature_names):
                    issue(filename, f"nodes[{index}].features",
                          "特征数量与feature_names不一致", True)
                    continue
                comparisons.update(zip(graph.feature_names, features, strict=True))
            elif isinstance(features, dict):
                comparisons.update(features)
            elif features is not None:
                issue(filename, f"nodes[{index}].features", "features须为数组或对象", True)
            if isinstance(raw.get("attributes"), dict):
                comparisons.update(raw["attributes"])
            for key, value in comparisons.items():
                stored = data.get(key, data["features"].get(key, data["attributes"].get(key)))
                present = key in data or key in data["features"] or key in data["attributes"]
                if present and stored != value:
                    issue(filename, f"nodes[{index}].{key}",
                          f"企业 {node.id} 的 {key} 与CSV转换值冲突；请核对来源，不自动覆盖", True)
        for kind, items in (("edge", graph.edges), ("hyperedge", graph.hyperedges)):
            for index, record in enumerate(items):
                raw = record.model_dump(exclude_none=True)
                refs = ([raw["source"], raw["target"]] if kind == "edge" else raw["members"])
                file_refs.update(refs)
                path = f"{'edges' if kind == 'edge' else 'hyperedges'}[{index}]"
                if any(ref not in companies for ref in refs):
                    issue(filename, path, "关联对象不在CSV转换结果中，须补充企业或调整关系文件")
                    continue
                relation_key = (
                    (kind, raw["source"], raw["target"], raw["relation"])
                    if kind == "edge" else (kind, raw["kind"], tuple(sorted(refs)))
                )
                if relation_key in seen:
                    if seen[relation_key] == raw:
                        graph_report["duplicateCount"] += 1
                    else:
                        issue(filename, path, "重复关系的权重或证据冲突，须明确保留规则", True)
                    continue
                seen[relation_key] = raw
                raw["sourceRecord"] = {"filename": filename, "sha256": sha, "path": path}
                output.append({"kind": kind, "snapshot": "import", "nodeId": None,
                               "source": raw.get("source"), "target": raw.get("target"),
                               "members": raw.get("members", []), "data": raw})
                # Deduplication compares input evidence, excluding generated provenance.
                seen[relation_key] = {k: v for k, v in raw.items() if k != "sourceRecord"}
                counts[kind] += 1
        referenced.update(file_refs)
        missing.update(file_refs - companies.keys())
        graph_report["files"].append({"filename": filename, "referencedCount": len(file_refs),
                                      "matchedCount": len(file_refs & companies.keys()),
                                      "missingCount": len(file_refs - companies.keys())})
    graph_report.update(referencedCount=len(referenced), matchedCount=len(referenced - missing),
                        missingCount=len(missing), missingIds=sorted(missing)[:20])
    report.update(counts=counts, graph=graph_report, outputCount=len(output),
                  warnings=["CSV提供企业属性，JSON提供关系；不补造节点、关系、训练划分或预测。",
                            "图JSON的额外节点属性仅作冲突核验；企业属性以已确认的CSV规则为准。"],
                  passed=report["issueCount"] == 0 and bool(companies))
    if len(json.dumps(output, ensure_ascii=False).encode()) > 16 * 1024 * 1024:
        raise ValueError("转换产物超过16 MiB限制，请拆分案例；完整英国数据请使用工作台ZIP适配器")
    return output, report
