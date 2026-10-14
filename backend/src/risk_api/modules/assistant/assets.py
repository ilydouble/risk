from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.company.model import Company
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseRecord


@dataclass(frozen=True)
class SessionAsset:
    id: str
    name: str
    kind: str
    row_count: int | None
    content: dict

    def descriptor(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind,
            "source": "data_preparation", "scope": "current_browser_session",
            "persistence": "browser_memory", "rowCount": self.row_count,
            "countMeaning": (
                "上传文件的体检行数" if self.row_count is not None else "不适用（报告）"
            ),
            "capabilities": ["asset_read"],
            "generation": "backend_language_model" if self.kind == "analysis_report" else None,
            "warnings": ["来自本轮浏览器快照，刷新后失效；未登记为训练数据集；内容未经独立核实。"],
        }


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
            "warnings": ["演示种子快照，评分和预测展示不代表真实在线模型结果。"],
        }

    async def datasets(self, owner: str, dataset_id: str | None = None) -> list[dict]:
        record_count = (
            select(func.count()).select_from(EnterpriseRecord)
            .where(EnterpriseRecord.dataset_id == Dataset.id).correlate(Dataset).scalar_subquery()
        )
        statement = select(Dataset.id, Dataset.name, Dataset.filename, record_count.label("count"))
        statement = statement.where(Dataset.owner_id == owner)
        if dataset_id is not None:
            statement = statement.where(Dataset.id == dataset_id)
        rows = (await self.session.execute(
            statement.order_by(Dataset.created_at.desc(), Dataset.id).limit(201)
        )).mappings().all()
        return [{
            "id": f"workbench:{row['id']}", "datasetId": row["id"], "name": row["name"],
            "filename": row["filename"], "kind": "training_dataset", "source": "workbench",
            "scope": "current_account", "persistence": "database", "rowCount": row["count"],
            "countMeaning": "已导入工作台的标准企业数据记录数（含关系、事件等）",
            "capabilities": ["asset_read", "workbench_ask"],
            "warnings": ["导入记录数不等于原始文件行数；未导入时为0。"],
        } for row in rows]

    async def enterprise_rows(self) -> dict:
        rows = (await self.session.execute(
            select(Company.id, Company.name_cn, Company.name_en, Company.reg_no, Company.region,
                   Company.sector).order_by(Company.id).limit(101)
        )).mappings().all()
        return {"rows": [dict(row) for row in rows[:100]], "truncated": len(rows) > 100}
