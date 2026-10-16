import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from risk_api.errors import AppError
from risk_api.modules.data_prep.case_files import build_case, unpack_source
from risk_api.modules.data_prep.model import Preparation
from risk_api.modules.data_prep.profile import inspect_csv
from risk_api.modules.data_prep.repository import PreparationRepository

ROLES = {"identity", "feature", "label", "relation", "time", "ignore", "unknown"}


def mapping_hint(role: str, field: dict) -> tuple[str, str]:
    if role == "identity":
        return "enterprise.id", "保留原始文本与前导零；检查缺失及重复标识，不自动合并"
    if role == "feature":
        method = ("数值解析；缺失填补和标准化仅在训练集拟合，再应用于验证/测试集"
                  if field["typeHint"] == "number" else
                  "类别编码仅在训练集拟合；验证/测试未知类别需独立处理")
        target = f"features.{field['name']}"
        return target if len(target) <= 128 else "", method
    if role == "label":
        return "enterprise.label", "待确认正负类业务含义和观察时点；不能把登记状态直接解释为违约"
    if role == "time":
        return "", "待确认用于观测时间还是数据划分；保留来源规则，不自动随机划分"
    if role == "relation":
        return "", "待确认关联表、两端实体字段、关系类型和构建依据；不能凭同组属性造边"
    return "", "" if role == "unknown" else "不进入模型输入"


def proposed_mapping(profile: dict, report: dict | None) -> list[dict]:
    suggestions = {item["field"]: item for item in (report or {}).get("suggestions", [])}
    result = []
    for field in profile["fields"]:
        suggestion = suggestions.get(field["name"], {})
        role = suggestion.get("role", "unknown")
        target, method = mapping_hint(role, field)
        result.append({
            "field": field["name"], "role": role,
            "target": suggestion.get("target") or target,
            "method": suggestion.get("method") or method,
            "reason": suggestion.get("reason", "请确认字段含义和转换方式")[:2000],
        })
    return result


def validate_mapping(profile: dict, mapping: list[dict], confirmed: bool) -> None:
    names = {field["name"] for field in profile["fields"]}
    if len(mapping) != len(names) or {item["field"] for item in mapping} != names:
        raise AppError(422, "DATA_PREP_MAPPING_INVALID", "映射须包含每个源字段且不能重复")
    if any(item["role"] not in ROLES for item in mapping):
        raise AppError(422, "DATA_PREP_MAPPING_INVALID", "字段用途无效")
    if confirmed:
        active = [item for item in mapping if item["role"] != "ignore"]
        if (
            any(item["role"] == "unknown" or not item["target"].strip()
                or not item["method"].strip() or "待确认" in item["target"]
                or "待确认" in item["method"] for item in active)
            or sum(item["role"] == "identity" for item in active) != 1
            or sum(item["role"] == "label" for item in active) > 1
            or not any(item["role"] == "feature" for item in active)
        ):
            raise AppError(422, "DATA_PREP_MAPPING_INVALID",
                           "请指定一个企业标识、至少一个特征，解决待确认字段，并填写目标与转换方式")
        targets = [item["target"].strip() for item in active]
        if len(set(targets)) != len(targets):
            raise AppError(422, "DATA_PREP_MAPPING_INVALID", "多个字段不能映射到同一个目标")


class PreparationService:
    def __init__(self, repository: PreparationRepository):
        self.repository = repository

    async def create_case(self, owner: str, files: list[tuple[str, bytes]],
                          previous_id: str | None = None) -> Preparation:
        previous = None
        if previous_id:
            previous = await self.repository.get(owner, previous_id)
            if hashlib.sha256(previous.source).hexdigest() != previous.source_sha:
                raise AppError(409, "DATA_PREP_PLAN_STALE", "原案例摘要异常，不能补充文件")
            existing_files = unpack_source(previous.source, previous.profile)
            if not previous.profile.get("caseFiles"):
                existing_files = [(previous.filename, previous.source)]
            files = existing_files + files
        content, profile = await asyncio.to_thread(build_case, files)
        if previous_id:
            profile["previousPreparationId"] = previous_id
        primary = next(name for name, _ in files if name.lower().endswith(".csv"))
        filename = primary if len(files) == 1 else f"{primary} 等{len(files)}个文件"
        return await self._persist(
            owner, filename, content, profile,
            deepcopy(previous.mapping) if previous else None,
            deepcopy(previous.conversion_plan) if previous else None,
        )

    async def create(self, owner: str, filename: str, content: bytes) -> Preparation:
        return await self._persist(owner, filename, content, inspect_csv(content))

    async def _persist(self, owner: str, filename: str, content: bytes,
                       profile: dict, mapping: list[dict] | None = None,
                       plan: dict | None = None) -> Preparation:
        existing = await self.repository.by_sha(owner, profile["sha256"])
        if existing is not None:
            return existing
        item = Preparation(id=str(uuid4()), owner_id=owner, filename=filename[:255], source=content,
                           source_sha=profile["sha256"], profile=profile, report=None,
                           mapping=(mapping if mapping is not None
                                    else proposed_mapping(profile, None)),
                           conversion_plan=plan or {},
                           confirmed=False, in_workbench=False)
        try:
            return await self.repository.save(item)
        except IntegrityError:
            await self.repository.session.rollback()
            existing = await self.repository.by_sha(owner, profile["sha256"])
            if existing is None:
                raise
            return existing

    async def report(self, owner: str, identity: str, report: dict) -> Preparation:
        item = await self.repository.get(owner, identity, lock=True)
        names = {field["name"] for field in item.profile["fields"]}
        if any(entry["field"] not in names or entry["role"] not in ROLES
               for entry in report.get("suggestions", [])):
            raise AppError(502, "DATA_PREP_SUGGESTION_INVALID", "报告映射引用了未知源字段或用途")
        item.report = report
        # New analysis must not overwrite a user's edited or confirmed mapping plan.
        if item.mapping == proposed_mapping(item.profile, None):
            item.mapping = proposed_mapping(item.profile, report)
        item.updated_at = datetime.now(UTC)
        return await self.repository.save(item)

    async def save_mapping(self, owner: str, identity: str, mapping: list[dict],
                           confirmed: bool, handoff: bool) -> Preparation:
        item = await self.repository.get(owner, identity, lock=True)
        validate_mapping(item.profile, mapping, confirmed)
        if handoff and not confirmed:
            raise AppError(422, "DATA_PREP_MAPPING_INVALID", "请确认映射方案后再转入工作台")
        item.mapping, item.confirmed = mapping, confirmed
        item.in_workbench = item.in_workbench or handoff
        item.updated_at = datetime.now(UTC)
        return await self.repository.save(item)
