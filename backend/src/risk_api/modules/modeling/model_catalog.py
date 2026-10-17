"""Published model discovery scoped to an account and its original dataset."""

from sqlalchemy import select

from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.service import ModelingService
from risk_api.modules.modeling.workbench_model import Dataset, ModelVersion, Run


class ModelCatalogService:
    def __init__(self, modeling: ModelingService):
        self.modeling = modeling

    async def list(
        self, owner: str, dataset_id: str | None, limit: int, model_id: str | None = None
    ) -> dict:
        if dataset_id:
            await self.modeling.repository.dataset(owner, dataset_id)
        query = select(ModelVersion, Dataset).join(Run, Run.id == ModelVersion.run_id).join(
            Dataset, Dataset.id == Run.dataset_id
        ).where(
            ModelVersion.owner_id == owner, Run.owner_id == owner, Dataset.owner_id == owner,
            ModelVersion.protocol_generation == 2, Run.protocol_generation == 2,
            Dataset.protocol_generation == 2,
        )
        if model_id:
            await self.modeling.repository.version(owner, model_id)
            query = query.where(ModelVersion.id == model_id)
        if dataset_id:
            query = query.where(Dataset.id == dataset_id)
        rows = (await self.modeling.session.execute(
            query.order_by(ModelVersion.created_at.desc(), ModelVersion.id).limit(limit + 1)
        )).all()
        return {
            "models": [{
                "modelId": version.id, "name": version.name,
                "datasetId": dataset.id, "datasetName": dataset.name,
                "createdAt": version.created_at.isoformat(), "runId": version.run_id,
                "algorithm": version.artifact.get("profile", {}).get("algorithm", "RiskGNN"),
                "target": version.artifact.get("profile", {}).get("target"),
                "metrics": version.artifact.get("report", {}).get("metrics", {}),
                "exampleCompanyIds": version.artifact.get("companies", [])[:5],
            } for version, dataset in rows[:limit]],
            "truncated": len(rows) > limit, "order": "createdAt_desc",
        }

    async def companies(self, owner: str, model_id: str, keyword: str, page: int) -> dict:
        version = await self.modeling.repository.version(owner, model_id)
        run = await self.modeling.repository.run(owner, version.run_id)
        result = await EnterpriseService(self.modeling).page(
            owner, run.dataset_id, "company", keyword, None, None, None, page, 20
        )
        # The published preview contains at most 100 IDs; it is not the full graph index.
        return {
            "modelId": model_id, "datasetId": run.dataset_id,
            "imported": result["imported"], "total": result["total"], "page": page,
            "pageSize": 20,
            "items": [{"companyId": row["nodeId"], "name": row["data"].get("name"),
                       "snapshot": row["snapshot"]} for row in result["items"]],
            "exampleCompanyIds": version.artifact.get("companies", [])[:10],
            "note": ("检索范围为模型所属数据集；子集训练不一定包含全部企业，"
                     "是否在绑定图内由预测服务校验。"),
        }
