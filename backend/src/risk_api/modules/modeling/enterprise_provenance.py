import asyncio
import hashlib

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from risk_api.modules.data_prep.conversion import ENGINE, ConversionPlan, digest
from risk_api.modules.data_prep.lineage import trace_company
from risk_api.modules.data_prep.model import Preparation, PreparationConversion
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport


def unavailable(message: str) -> dict:
    return {"status": "unavailable", "message": message}


async def enterprise_provenance(
    session: AsyncSession,
    owner: str,
    dataset: Dataset,
    imported: EnterpriseImport | None,
    company: dict,
) -> dict:
    task_id = imported.manifest.get("taskId") if imported else None
    if not task_id or not dataset.source_preparation_id:
        return unavailable("此来源未提供原始CSV行级追溯；下方属性仍是当前数据集已保存的值。")
    row = (
        await session.execute(
            select(PreparationConversion, Preparation)
            .options(defer(PreparationConversion.output))
            .join(Preparation, Preparation.id == PreparationConversion.preparation_id)
            .where(
                PreparationConversion.id == task_id,
                PreparationConversion.dataset_id == dataset.id,
                PreparationConversion.owner_id == owner,
                Preparation.owner_id == owner,
                Preparation.id == dataset.source_preparation_id,
                PreparationConversion.status == "imported",
            )
        )
    ).first()
    if row is None:
        return unavailable("原始案例或已导入转换任务不可用，无法核验行级来源。")
    task, source = row
    if task.engine_version != ENGINE:
        return unavailable("此转换版本暂不支持行级还原；未使用当前规则猜测历史来源。")
    if (
        hashlib.sha256(source.source).hexdigest() != task.source_sha
        or source.source_sha != task.source_sha
        or dataset.mapping_snapshot.get("sourceSha256") != task.source_sha
        or dataset.mapping_snapshot.get("outputSha256") != task.output_sha
        or dataset.mapping_snapshot.get("plan") != task.plan
        or imported is None
        or imported.sha256 != task.output_sha
        or digest([task.engine_version, task.source_sha, task.mapping_digest, task.plan])
        != task.fingerprint
    ):
        return unavailable("原文件或冻结规则的摘要不一致，暂不展示未经核验的来源。")
    try:
        plan = ConversionPlan.model_validate(task.plan)
        lineage = await asyncio.to_thread(
            trace_company, source.source, plan, company["nodeId"], company["data"]
        )
    except (ValueError, KeyError, ValidationError):
        return unavailable("原始行与已保存企业记录无法对应，暂不展示未经核验的来源。")
    return {
        "status": "available",
        "message": "已按导入时冻结规则核验原始行与当前企业记录。",
        "preparationId": source.id,
        "filename": source.filename,
        "taskId": task.id,
        "engineVersion": task.engine_version,
        "planVersion": task.fingerprint,
        "sourceSha256": task.source_sha,
        "outputSha256": task.output_sha,
        "labelMeaning": plan.labelMeaning,
        "deduplicate": plan.deduplicate,
        "importedAt": imported.created_at.isoformat(),
        **lineage,
    }
