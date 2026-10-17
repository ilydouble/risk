from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.company.model import Company
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseRecord
from risk_api.modules.overview.repository import OverviewRepository


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def singapore_snapshot(self, identity: str | None = None) -> dict | None:
        snapshot = await OverviewRepository(self.session).latest()
        if snapshot is None or (identity is not None and snapshot.id != identity):
            return None
        payload = snapshot.payload
        samples = payload.get("sampleCompanies", [])
        asset = {
            "id": f"singapore-snapshot:{snapshot.id}", "name": "新加坡演示数据 · 真实来源统计快照",
            "kind": "enterprise_snapshot", "source": "singapore_demo",
            "scope": "shared_demo", "persistence": "database",
            "rowCount": payload["stats"]["companyCount"],
            "countMeaning": "原始新加坡数据集全量企业聚合数，并非可检索样本数",
            "searchableSampleCount": len(samples),
            "sourceSha256": snapshot.source_sha256, "capabilities": ["asset_read"],
            "warnings": ["共享演示用途，不计入当前账号的上传数量或个人企业统计。",
                         "真实来源历史快照，固定样本不代表总体分布；标签不是实时模型预测。"],
        }
        return {"asset": asset, "dataset": payload["dataset"],
                "statistics": payload["stats"], "sampling": payload.get("sampling", {}),
                "rows": samples[:100], "truncated": len(samples) > 100}

    async def enterprise_directory(self) -> dict:
        regions = (await self.session.execute(
            select(Company.region, func.count().label("count"))
            .group_by(Company.region).order_by(Company.region)
        )).mappings().all()
        return {
            "id": "enterprise-directory", "name": "企业演示目录（含新加坡案例）",
            "kind": "enterprise_directory", "source": "enterprise_demo",
            "scope": "shared_demo", "persistence": "database",
            "rowCount": sum(row["count"] for row in regions),
            "countMeaning": "企业目录记录数", "regions": [dict(row) for row in regions],
            "capabilities": ["asset_read"],
            "warnings": ["界面演示种子，评分和预测展示不代表真实在线模型结果。",
                         "与新加坡来源统计快照不同；不计入个人上传统计，不能合并企业数。"],
        }

    async def datasets(self, owner: str, dataset_id: str | None = None) -> list[dict]:
        record_count = (
            select(func.count()).select_from(EnterpriseRecord)
            .where(EnterpriseRecord.dataset_id == Dataset.id).correlate(Dataset).scalar_subquery()
        )
        statement = select(Dataset.id, Dataset.name, Dataset.filename, Dataset.execution,
                           Dataset.source_preparation_id, record_count.label("count"))
        statement = statement.where(Dataset.owner_id == owner)
        if dataset_id is not None:
            statement = statement.where(Dataset.id == dataset_id)
        rows = (await self.session.execute(
            statement.order_by(Dataset.created_at.desc(), Dataset.id).limit(201)
        )).mappings().all()
        return [{
            "id": f"workbench:{row['id']}", "datasetId": row["id"], "name": row["name"],
            "filename": row["filename"],
            "kind": "enterprise_dataset" if row["execution"].get("result", {}).get("browseOnly")
            else "training_dataset", "source": "workbench",
            "sourcePreparationId": row["source_preparation_id"],
            "browseOnly": bool(row["execution"].get("result", {}).get("browseOnly")),
            "scope": "current_account", "persistence": "database", "rowCount": row["count"],
            "countMeaning": "已导入工作台的标准企业数据记录数（含关系、事件等）",
            "capabilities": ["asset_read", "workbench_ask"],
            "warnings": ["导入记录数不等于原始文件行数；未导入时为0。",
                         "原案例与派生数据集为同一来源的不同阶段，记录数不能相加。",
                         *(["CSV转换企业数据只供浏览和问数，尚未形成训练输入。"]
                           if row["execution"].get("result", {}).get("browseOnly") else [])],
        } for row in rows]

    async def enterprise_rows(self) -> dict:
        rows = (await self.session.execute(
            select(Company.id, Company.name_cn, Company.name_en, Company.reg_no, Company.region,
                   Company.sector).order_by(Company.id).limit(101)
        )).mappings().all()
        return {"rows": [dict(row) for row in rows[:100]], "truncated": len(rows) > 100}
