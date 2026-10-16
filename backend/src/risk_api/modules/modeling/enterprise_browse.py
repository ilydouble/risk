"""Dataset-scoped overview, company detail and prediction provenance."""

from sqlalchemy import Float, cast, func, select

from risk_api.errors import AppError
from risk_api.modules.modeling.enterprise_provenance import enterprise_provenance
from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.service import ModelingService
from risk_api.modules.modeling.workbench_model import (
    Dataset,
    EnterpriseImport,
    EnterprisePrediction,
    EnterpriseRecord,
    ModelVersion,
    Run,
)


def source_data(dataset: Dataset, imported: EnterpriseImport | None) -> dict:
    status = dataset.execution.get("status", "queued")
    result = dataset.execution.get("result", {})
    sync = dataset.execution.get("enterpriseSync", {})
    available = result.get("enterpriseArtifact", {}).get("format") == "risk-enterprise-data-v1"
    import_status = (
        "ready"
        if imported
        else "failed"
        if status in {"failed", "cancelled"}
        else "unavailable"
        if status == "completed" and not available
        else "failed"
        if sync.get("status") == "failed"
        else "pending"
    )
    return {
        "id": dataset.id,
        "name": dataset.name,
        "status": status,
        "importStatus": import_status,
        "importError": sync.get("errorCode") if not imported else None,
        "counts": imported.counts if imported else {},
        "createdAt": dataset.created_at.isoformat(),
    }


class EnterpriseBrowseService:
    def __init__(self, modeling: ModelingService):
        self.modeling, self.session = modeling, modeling.session

    async def sources(self, owner: str, page: int, size: int) -> dict:
        condition = (
            (Dataset.owner_id == owner) & (Dataset.protocol_generation == 2) & Dataset.confirmed
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Dataset).where(condition)
        )
        rows = await self.session.execute(
            select(Dataset, EnterpriseImport)
            .outerjoin(EnterpriseImport, EnterpriseImport.dataset_id == Dataset.id)
            .where(condition)
            .order_by(Dataset.created_at.desc(), Dataset.id)
            .offset((page - 1) * size)
            .limit(size)
        )
        return {
            "items": [source_data(dataset, imported) for dataset, imported in rows],
            "total": total or 0,
            "page": page,
            "pageSize": size,
        }

    async def overview(self, owner: str, identity: str) -> dict:
        dataset = await self.modeling.repository.dataset(owner, identity)
        imported = await self.session.get(EnterpriseImport, identity)
        label_value = EnterpriseRecord.data["label"].astext
        labels = await self.session.execute(
            select(label_value, func.count())
            .where(EnterpriseRecord.dataset_id == identity, EnterpriseRecord.kind == "company")
            .group_by(label_value)
        )
        label_counts = {"positive": 0, "negative": 0, "unlabeled": 0}
        for label, count in labels:
            key = "positive" if label == "1" else "negative" if label == "0" else "unlabeled"
            label_counts[key] += count
        prediction = EnterprisePrediction
        models = await self.session.execute(
            select(
                ModelVersion.id,
                ModelVersion.name,
                func.count(prediction.company_id),
                func.count(prediction.company_id).filter(
                    prediction.result["predictedLabel"].astext == "1"
                ),
                func.avg(cast(prediction.result["probability"].astext, Float)),
                func.avg(cast(prediction.result["uncertainty"].astext, Float)),
            )
            .join(Run, Run.id == ModelVersion.run_id)
            .outerjoin(
                prediction,
                (prediction.model_id == ModelVersion.id) & (prediction.dataset_id == identity),
            )
            .where(
                Run.dataset_id == identity,
                Run.owner_id == owner,
                ModelVersion.owner_id == owner,
                Run.protocol_generation == 2,
                ModelVersion.protocol_generation == 2,
            )
            .group_by(ModelVersion.id, ModelVersion.name)
            .order_by(ModelVersion.created_at.desc())
        )
        samples = await EnterpriseService(self.modeling).page(
            owner, identity, "company", "", None, None, None, 1, 8
        )
        return {
            "dataset": source_data(dataset, imported),
            "labels": label_counts,
            "target": imported.manifest.get("target") if imported else None,
            "models": [
                {
                    "id": mid,
                    "name": name,
                    "predictionCount": count,
                    "positiveCount": positive,
                    "averageProbability": probability,
                    "averageUncertainty": uncertainty,
                }
                for mid, name, count, positive, probability, uncertainty in models
            ],
            "companies": samples["items"],
        }

    async def company(self, owner: str, identity: str, node: str, model: str | None) -> dict:
        dataset = await self.modeling.repository.dataset(owner, identity)
        rows = await EnterpriseService(self.modeling).page(
            owner, identity, "company", "", node, None, model, 1, 1
        )
        if not rows["items"]:
            raise AppError(
                404, "MODELING_COMPANY_NOT_FOUND", "Enterprise not found in this dataset"
            )
        company = rows["items"][0]
        related = {}
        for kind in ("edge", "hyperedge", "event"):
            page = await EnterpriseService(self.modeling).page(
                owner, identity, kind, "", node, company["snapshot"], None, 1, 20
            )
            related[kind] = {"items": page["items"], "total": page["total"]}
        predictions = await self.session.execute(
            select(ModelVersion.id, ModelVersion.name, EnterprisePrediction.result)
            .join(EnterprisePrediction, EnterprisePrediction.model_id == ModelVersion.id)
            .join(Run, Run.id == ModelVersion.run_id)
            .where(
                ModelVersion.owner_id == owner,
                Run.owner_id == owner,
                Run.dataset_id == identity,
                EnterprisePrediction.dataset_id == identity,
                EnterprisePrediction.company_id == node,
            )
            .order_by(ModelVersion.created_at.desc())
            .limit(100)
        )
        imported = await self.session.get(EnterpriseImport, identity)
        return {
            "dataset": source_data(dataset, imported),
            "company": company,
            "provenance": await enterprise_provenance(self.session, owner, dataset,
                                                       imported, company),
            "related": related,
            "predictions": [
                {"modelId": mid, "modelName": name, "result": result}
                for mid, name, result in predictions
            ],
        }
