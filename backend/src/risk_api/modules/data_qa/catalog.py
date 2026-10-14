"""Business names and approved SQLAlchemy projections over workbench tables."""

from sqlalchemy import Float, cast, func, select

from risk_api.modules.modeling.workbench_model import (
    Dataset as D,
)
from risk_api.modules.modeling.workbench_model import (
    EnterpriseImport as I,
)
from risk_api.modules.modeling.workbench_model import (
    EnterprisePrediction as P,
)
from risk_api.modules.modeling.workbench_model import (
    EnterpriseRecord as E,
)
from risk_api.modules.modeling.workbench_model import (
    ModelVersion as M,
)
from risk_api.modules.modeling.workbench_model import (
    Run as R,
)

# Type is also used by the compiler to reject nonsensical numeric operations.
COMMON = {"dataset_id": ("数据集ID", "text"), "dataset_name": ("数据集名称", "text")}
CATALOG = {
    "datasets": (
        "数据集",
        "workbench_datasets",
        {
            **COMMON,
            "filename": ("文件名", "text"),
            "size": ("文件字节数", "number"),
            "status": ("校验状态", "text"),
            "created_at": ("创建时间", "datetime"),
        },
    ),
    "runs": (
        "训练实验",
        "workbench_runs",
        {
            **COMMON,
            "run_id": ("实验ID", "text"),
            "name": ("实验名称", "text"),
            "algorithm": ("算法标识", "text"),
            "status": ("执行状态", "text"),
            "created_at": ("创建时间", "datetime"),
        },
    ),
    "models": (
        "已登记模型",
        "workbench_model_versions",
        {
            **COMMON,
            "model_id": ("模型ID", "text"),
            "name": ("模型名称", "text"),
            "run_id": ("来源实验ID", "text"),
            "created_at": ("登记时间", "datetime"),
        },
    ),
    "imports": (
        "企业导入摘要",
        "workbench_enterprise_imports",
        {
            **COMMON,
            "counts": ("各类导入记录数JSON", "json"),
            "created_at": ("导入时间", "datetime"),
        },
    ),
    "records": (
        "全部标准企业数据记录",
        "workbench_enterprise_records",
        {
            **COMMON,
            "sequence": ("行序号", "number"),
            "kind": ("类型", "text"),
            "snapshot": ("快照/划分", "text"),
            "node_id": ("节点ID", "text"),
            "name": ("节点名称", "text"),
            "source": ("关系起点/事件企业", "text"),
            "target": ("关系终点", "text"),
            "members": ("超边成员JSON", "json"),
            "attributes": ("原始属性JSON", "json"),
            "label": ("已有标签", "text"),
        },
    ),
    "enterprises": (
        "企业（仅company记录）",
        "workbench_enterprise_records",
        {
            **COMMON,
            "sequence": ("行序号", "number"),
            "company_id": ("企业ID", "text"),
            "name": ("企业名称", "text"),
            "snapshot": ("快照/划分", "text"),
            "attributes": ("原始属性JSON", "json"),
            "label": ("已有标签", "text"),
        },
    ),
    "predictions": (
        "已保存的模型预测",
        "workbench_enterprise_predictions",
        {
            **COMMON,
            "model_id": ("模型ID", "text"),
            "model_name": ("模型名称", "text"),
            "company_id": ("企业ID", "text"),
            "name": ("企业名称（如已导入）", "text"),
            "probability": ("主分类正类概率（未校准）", "number"),
            "predicted_label": ("预测类别0/1", "number"),
            "fused_probability": ("融合证据概率", "number"),
            "uncertainty": ("证据不确定性", "number"),
            "conflict": ("证据冲突", "number"),
            "created_at": ("预测保存时间", "datetime"),
        },
    ),
}


def sources(owner: str):
    common = [D.id.label("dataset_id"), D.name.label("dataset_name")]
    owned = D.owner_id == owner
    dataset = select(
        *common,
        D.filename,
        D.size,
        func.coalesce(D.execution["status"].astext, "pending_upload").label("status"),
        D.created_at,
    ).where(owned)
    runs = (
        select(
            *common,
            R.id.label("run_id"),
            R.name,
            R.configuration["resolvedParameters"]["algorithm"].astext.label("algorithm"),
            func.coalesce(R.execution["status"].astext, "queued").label("status"),
            R.created_at,
        )
        .select_from(R)
        .join(D, D.id == R.dataset_id)
        .where(owned, R.owner_id == owner)
    )
    models = (
        select(*common, M.id.label("model_id"), M.name, M.run_id, M.created_at)
        .select_from(M)
        .join(R, R.id == M.run_id)
        .join(D, D.id == R.dataset_id)
        .where(owned, R.owner_id == owner, M.owner_id == owner)
    )
    imports = (
        select(*common, I.counts, I.created_at)
        .select_from(I)
        .join(D, D.id == I.dataset_id)
        .where(owned)
    )
    records = (
        select(
            *common,
            E.sequence,
            E.kind,
            E.snapshot,
            E.node_id,
            E.data["name"].astext.label("name"),
            E.source,
            E.target,
            E.members,
            E.data["attributes"].label("attributes"),
            E.data["label"].astext.label("label"),
        )
        .select_from(E)
        .join(D, D.id == E.dataset_id)
        .where(owned)
    )
    companies = (
        select(
            *common,
            E.sequence,
            E.node_id.label("company_id"),
            E.data["name"].astext.label("name"),
            E.snapshot,
            E.data["attributes"].label("attributes"),
            E.data["label"].astext.label("label"),
        )
        .select_from(E)
        .join(D, D.id == E.dataset_id)
        .where(owned, E.kind == "company")
    )
    numeric = {
        "probability": "probability",
        "predicted_label": "predictedLabel",
        "fused_probability": "fusedProbability",
        "uncertainty": "uncertainty",
        "conflict": "conflict",
    }
    predictions = (
        select(
            *common,
            M.id.label("model_id"),
            M.name.label("model_name"),
            P.company_id,
            E.data["name"].astext.label("name"),
            *[cast(P.result[key].astext, Float).label(name) for name, key in numeric.items()],
            P.created_at,
        )
        .select_from(P)
        .join(D, D.id == P.dataset_id)
        .join(M, M.id == P.model_id)
        .join(R, (R.id == M.run_id) & (R.dataset_id == D.id))
        .outerjoin(
            E, (E.dataset_id == P.dataset_id) & (E.node_id == P.company_id) & (E.kind == "company")
        )
        .where(owned, M.owner_id == owner, R.owner_id == owner)
    )
    return dict(
        zip(CATALOG, [dataset, runs, models, imports, records, companies, predictions], strict=True)
    )


def describe() -> list[dict]:
    return [
        {
            "id": name,
            "name": title,
            "physicalTable": physical,
            "fields": [
                {"id": field, "name": label, "type": kind}
                for field, (label, kind) in fields.items()
            ],
        }
        for name, (title, physical, fields) in CATALOG.items()
    ]
