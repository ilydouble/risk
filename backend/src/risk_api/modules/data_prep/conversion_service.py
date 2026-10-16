import asyncio
import hashlib
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from risk_api.errors import AppError
from risk_api.modules.data_prep.case_files import CASE_ENGINE, execute_case
from risk_api.modules.data_prep.conversion import ENGINE, ConversionPlan, digest, execute
from risk_api.modules.data_prep.model import PreparationConversion
from risk_api.modules.data_prep.repository import PreparationRepository
from risk_api.modules.modeling.enterprise_data import FORMAT, NormalizedRecord
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport, EnterpriseRecord


class ConversionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.preparations = PreparationRepository(session)

    async def save_plan(self, owner: str, identity: str, plan: ConversionPlan) -> dict:
        item = await self.preparations.get(owner, identity, lock=True)
        source_fields = {f["name"] for f in item.profile["fields"]}
        supplied = {rule.field for rule in plan.columns}
        if supplied != source_fields:
            raise AppError(
                422,
                "DATA_PREP_RULE_INVALID",
                f"规则字段与当前CSV不一致。缺少：{sorted(source_fields - supplied)}；"
                f"不存在：{sorted(supplied - source_fields)}。"
                "请重新读取案例；未使用字段须显式忽略。",
            )
        mapping = []
        for rule in plan.columns:
            role = (
                "ignore"
                if rule.type == "ignore"
                else "identity"
                if rule.target == "enterprise.id"
                else "label"
                if rule.type == "label"
                else "feature"
            )
            mapping.append(
                {
                    "field": rule.field,
                    "role": role,
                    "target": rule.target,
                    "method": f"{rule.type}; missing={rule.missing}",
                    "reason": "可执行规则；具体取值与标签含义见转换方案",
                }
            )
        item.mapping, item.confirmed = mapping, False
        item.conversion_plan = {"rules": plan.model_dump(), "mappingDigest": digest(mapping)}
        item.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.state(owner, identity)

    async def state(self, owner: str, identity: str, task_id: str | None = None) -> dict:
        item = await self.preparations.get(owner, identity)
        query = (
            select(PreparationConversion)
            .options(defer(PreparationConversion.output))
            .where(
                PreparationConversion.owner_id == owner,
                PreparationConversion.preparation_id == identity,
            )
        )
        if task_id:
            query = query.where(PreparationConversion.id == task_id)
        engine = CASE_ENGINE if item.profile.get("caseFiles") else ENGINE
        fingerprint = digest(
            [engine, item.source_sha, digest(item.mapping), item.conversion_plan.get("rules")]
        )
        task = await self.session.scalar(
            query.order_by(
                (PreparationConversion.fingerprint == fingerprint).desc(),
                PreparationConversion.created_at.desc(),
                PreparationConversion.id,
            ).limit(1)
        )
        if task_id and task is None:
            raise AppError(404, "DATA_PREP_TASK_NOT_FOUND", "转换任务不存在或无权访问")
        current = bool(
            item.conversion_plan
            and item.conversion_plan.get("mappingDigest") == digest(item.mapping)
        )
        return {
            "preparationId": identity,
            "plan": item.conversion_plan.get("rules"),
            "planCurrent": current,
            "task": None
            if task is None
            else {
                "id": task.id,
                "engineVersion": task.engine_version,
                "planVersion": task.fingerprint,
                "status": task.status,
                "sourceSha256": task.source_sha,
                "outputSha256": task.output_sha,
                "plan": task.plan,
                "report": task.report,
                "datasetId": task.dataset_id,
                "current": current
                and task.engine_version == engine
                and task.mapping_digest == digest(item.mapping)
                and task.plan == item.conversion_plan.get("rules")
                and task.source_sha == item.source_sha,
            },
        }

    async def trial(self, owner: str, identity: str) -> dict:
        item = await self.preparations.get(owner, identity, lock=True)
        if not item.conversion_plan or item.conversion_plan.get("mappingDigest") != digest(
            item.mapping
        ):
            raise AppError(
                409, "DATA_PREP_PLAN_STALE", "请先保存可执行规则；映射已修改则须重新核对规则"
            )
        plan = ConversionPlan.model_validate(item.conversion_plan["rules"])
        if hashlib.sha256(item.source).hexdigest() != item.source_sha:
            raise AppError(409, "DATA_PREP_PLAN_STALE", "原文件摘要不一致，请重新保存案例")
        mapping_digest = digest(item.mapping)
        engine = CASE_ENGINE if item.profile.get("caseFiles") else ENGINE
        fingerprint = digest([engine, item.source_sha, mapping_digest, plan.model_dump()])
        previous = await self.session.scalar(
            select(PreparationConversion).where(
                PreparationConversion.owner_id == owner,
                PreparationConversion.preparation_id == identity,
                PreparationConversion.fingerprint == fingerprint,
            )
        )
        if previous is None:
            try:
                if engine == CASE_ENGINE:
                    output, report = await asyncio.to_thread(execute_case, item.source,
                                                            item.profile, plan)
                else:
                    output, report = await asyncio.to_thread(execute, item.source, plan)
            except ValueError as error:
                raise AppError(422, "DATA_PREP_RULE_INVALID", str(error)) from error
            task = PreparationConversion(
                id=str(uuid4()),
                owner_id=owner,
                preparation_id=identity,
                fingerprint=fingerprint,
                engine_version=engine,
                source_sha=item.source_sha,
                mapping_digest=mapping_digest,
                plan=plan.model_dump(),
                output=output,
                output_sha=digest(output),
                report=report,
                status="ready" if report["passed"] else "blocked",
            )
            self.session.add(task)
            await self.session.commit()
            task_id = task.id
        else:
            task_id = previous.id
            await self.session.commit()
        return await self.state(owner, identity, task_id)

    async def import_task(self, owner: str, identity: str, task_id: str) -> dict:
        # Lock preparation first in every mutation to serialize edits, trials and imports.
        item = await self.preparations.get(owner, identity, lock=True)
        task = await self.session.scalar(
            select(PreparationConversion)
            .where(
                PreparationConversion.owner_id == owner,
                PreparationConversion.preparation_id == identity,
                PreparationConversion.id == task_id,
            )
            .with_for_update()
        )
        if task is None:
            raise AppError(404, "DATA_PREP_TASK_NOT_FOUND", "转换任务不存在或无权访问")
        if task.dataset_id:
            return await self.state(owner, identity, task_id)
        engine = CASE_ENGINE if item.profile.get("caseFiles") else ENGINE
        if (
            task.status != "ready"
            or task.engine_version != engine
            or not task.report.get("passed")
            or not task.output
            or hashlib.sha256(item.source).hexdigest() != task.source_sha
            or task.source_sha != item.source_sha
            or task.mapping_digest != digest(item.mapping)
            or task.plan != item.conversion_plan.get("rules")
            or digest(task.output) != task.output_sha
            or task.report.get("outputCount") != len(task.output)
        ):
            raise AppError(409, "DATA_PREP_PLAN_STALE", "结果未通过核验或方案已变化，请重新试运行")
        # Revalidate the persisted artifact, not the assistant's interpretation of its report.
        for record in task.output:
            NormalizedRecord.model_validate(record)
        companies = {r["nodeId"] for r in task.output if r["kind"] == "company"}
        if len(companies) != sum(r["kind"] == "company" for r in task.output):
            raise AppError(409, "DATA_PREP_PLAN_STALE", "转换产物标识冲突，请重新试运行")
        dataset_id = str(uuid4())
        for record in task.output:
            refs = ([record["source"], record["target"]] if record["kind"] == "edge"
                    else record.get("members", []))
            if any(ref not in companies for ref in refs):
                raise AppError(409, "DATA_PREP_PLAN_STALE", "关系引用无效，请重新试运行")
        counts = dict(Counter(r["kind"] for r in task.output))
        manifest = {
            "format": FORMAT,
            "sourceSha256": task.source_sha,
            "target": task.plan.get("labelMeaning") or None,
            "engine": engine,
            "taskId": task.id,
            "browseOnly": True,
            "protocol": engine,
            "counts": counts,
            "caseFiles": item.profile.get("caseFiles", []),
            "datasetProfile": {"browseOnly": True},
        }
        self.session.add(
            Dataset(
                id=dataset_id,
                owner_id=owner,
                name=item.filename[:128],
                filename=item.filename,
                object_key=f"preparations/{owner}/{task.id}",
                content_type="application/json" if engine == CASE_ENGINE else "text/csv",
                size=len(item.source),
                confirmed=True,
                source_preparation_id=identity,
                mapping_snapshot={
                    "mapping": deepcopy(item.mapping),
                    "plan": task.plan,
                    "sourceSha256": task.source_sha,
                    "outputSha256": task.output_sha,
                },
                execution={
                    "status": "completed",
                    "result": {
                        "browseOnly": True,
                        "supportedRunnerIds": [],
                        "enterpriseData": {"counts": counts},
                        "sha256": task.source_sha,
                    },
                },
            )
        )
        await self.session.flush()
        self.session.add(
            EnterpriseImport(
                dataset_id=dataset_id, sha256=task.output_sha, manifest=manifest, counts=counts
            )
        )
        await self.session.flush()
        for offset in range(0, len(task.output), 500):
            batch = [
                {
                    "dataset_id": dataset_id,
                    "sequence": offset + index + 1,
                    "kind": r["kind"],
                    "snapshot": r["snapshot"],
                    "node_id": r["nodeId"],
                    "source": r.get("source"),
                    "target": r.get("target"),
                    "members": r.get("members", []),
                    "data": r["data"],
                }
                for index, r in enumerate(task.output[offset : offset + 500])
            ]
            await self.session.execute(insert(EnterpriseRecord), batch)
        task.dataset_id, task.status = dataset_id, "imported"
        await self.session.commit()
        return await self.state(owner, identity, task_id)
