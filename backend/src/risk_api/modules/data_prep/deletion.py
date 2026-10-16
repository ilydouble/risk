"""Owner-scoped, previewed deletion of preparation-owned database artifacts."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.errors import AppError
from risk_api.modules.data_prep.conversion import digest
from risk_api.modules.data_prep.model import Preparation, PreparationConversion
from risk_api.modules.data_prep.repository import PreparationRepository
from risk_api.modules.modeling.workbench_model import (
    Dataset,
    EnterpriseImport,
    EnterprisePrediction,
    EnterpriseRecord,
    Run,
)


async def deletion_scope(session: AsyncSession, owner: str, identity: str,
                         *, lock: bool = False) -> dict:
    case = await PreparationRepository(session).get(owner, identity, lock=lock)
    query = select(Dataset).where(Dataset.source_preparation_id == identity).order_by(Dataset.id)
    if lock:
        query = query.with_for_update()
    datasets = list(await session.scalars(query))
    ids = [dataset.id for dataset in datasets]
    tasks = list((await session.execute(
        select(PreparationConversion.id, PreparationConversion.dataset_id,
               PreparationConversion.status)
        .where(PreparationConversion.preparation_id == identity).order_by(PreparationConversion.id)
    )).all())
    records = dict((await session.execute(
        select(EnterpriseRecord.kind, func.count()).where(EnterpriseRecord.dataset_id.in_(ids))
        .group_by(EnterpriseRecord.kind)
    )).all())
    predictions = await session.scalar(select(func.count()).select_from(EnterprisePrediction)
                                      .where(EnterprisePrediction.dataset_id.in_(ids))) or 0
    runs = await session.scalar(select(func.count()).select_from(Run)
                               .where(Run.dataset_id.in_(ids))) or 0
    descendants = list(await session.scalars(select(Preparation.id).where(
        Preparation.owner_id == owner,
        Preparation.profile["previousPreparationId"].astext == identity,
    ).order_by(Preparation.id)))
    reason = None
    if descendants:
        reason = "此案例还有补充文件后的版本，请先删除后续版本，避免丢失版本来源。"
    if runs:
        reason = "关联数据集已有训练或实验任务，请先处理模型工作台中的依赖。"
    if any(dataset.owner_id != owner or not dataset.object_key.startswith("preparations/")
           for dataset in datasets) or any(t.dataset_id and t.dataset_id not in ids for t in tasks):
        reason = "存在独立上传数据包或不属于本案例的关联产物，不能通过案例按钮删除。"
    counts = {"files": len(case.profile.get("caseFiles") or [case.filename]),
              "reports": int(case.report is not None), "tasks": len(tasks),
              "datasets": len(ids), "predictions": predictions, "records": records}
    revision = digest([identity, case.updated_at.isoformat(), ids,
                       [list(task) for task in tasks], counts, descendants, runs, reason])
    return {"preparationId": identity, "filename": case.filename, "revision": revision,
            "counts": counts, "datasetIds": ids, "blockedReason": reason, "deleted": False}


async def delete_preparation(session: AsyncSession, owner: str, identity: str,
                             revision: str) -> dict:
    scope = await deletion_scope(session, owner, identity, lock=True)
    if scope["blockedReason"]:
        raise AppError(409, "DATA_PREP_DELETE_BLOCKED", scope["blockedReason"])
    if scope["revision"] != revision:
        raise AppError(409, "DATA_PREP_DELETE_STALE",
                       "案例或关联数据已变化，请重新查看删除范围并确认")
    ids = scope["datasetIds"]
    # Match the conversion lock order; deletion and imports cannot interleave for this case.
    await session.execute(delete(EnterprisePrediction).where(
        EnterprisePrediction.dataset_id.in_(ids)
    ))
    await session.execute(delete(PreparationConversion).where(
        PreparationConversion.preparation_id == identity,
        PreparationConversion.owner_id == owner,
    ))
    await session.execute(delete(EnterpriseRecord).where(EnterpriseRecord.dataset_id.in_(ids)))
    await session.execute(delete(EnterpriseImport).where(EnterpriseImport.dataset_id.in_(ids)))
    await session.execute(delete(Dataset).where(Dataset.id.in_(ids), Dataset.owner_id == owner))
    await session.execute(delete(Preparation).where(Preparation.id == identity,
                                                   Preparation.owner_id == owner))
    await session.commit()
    return {**scope, "deleted": True}
