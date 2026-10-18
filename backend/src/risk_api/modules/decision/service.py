"""Business ownership and synchronous inference records; execution stays in model-service."""

import hashlib
import json
import logging
from uuid import uuid4

from risk_api.errors import AppError
from risk_api.modules.decision.client import DecisionClient
from risk_api.modules.decision.contracts import (
    FinancialCompany,
    FinancialDataset,
    FinancialModelInfo,
    FinancialModelResult,
    FinancialScore,
    FinancialSource,
    RegisteredFinancialModel,
    SavedFinancialPrediction,
)
from risk_api.modules.decision.model import DeployedFinancialModel, FinancialPrediction
from risk_api.modules.decision.repository import DecisionRepository
from risk_api.modules.modeling.workbench_model import EnterpriseImport
from risk_api.shared.logging import current_request_id

logger = logging.getLogger(__name__)


def adapter_identity(imported: EnterpriseImport) -> tuple[str, str]:
    adapter = imported.manifest.get("datasetContract", {}).get("adapter", {})
    return str(adapter.get("id", "")), str(adapter.get("version", ""))


def require_adapter(info: FinancialModelInfo, imported: EnterpriseImport) -> tuple[str, str]:
    identity = adapter_identity(imported)
    if identity not in {(item.id, item.version) for item in info.supportedAdapters}:
        raise AppError(
            422,
            "DECISION_DATASET_UNSUPPORTED",
            "此数据集未提供财务模型输入，请使用财务观测数据集。",
            field="datasetId",
        )
    return identity


class DecisionService:
    def __init__(self, repository: DecisionRepository, client: DecisionClient):
        self.repository, self.client = repository, client
        self.session = repository.session

    async def catalog(self, owner: str) -> dict:
        status = await self.client.status()
        if not status.ready or status.model is None:
            return {"ready": False, "model": None, "datasets": [], "errorCode": status.errorCode}
        info = status.model
        async with self.session.begin():
            model = await self.repository.model(info)
            rows = await self.repository.datasets(owner)
            allowed = {(item.id, item.version) for item in info.supportedAdapters}
            datasets = [
                FinancialDataset(
                    datasetId=dataset.id,
                    name=dataset.name,
                    adapterId=adapter_identity(imported)[0],
                    adapterVersion=adapter_identity(imported)[1],
                    recordCount=imported.counts.get("company", 0),
                )
                for dataset, imported in rows
                if adapter_identity(imported) in allowed
            ]
            return {
                "ready": True,
                "model": RegisteredFinancialModel(id=model.id, **info.model_dump()),
                "datasets": datasets,
                "errorCode": None,
            }

    async def companies(
        self, owner: str, dataset_id: str, keyword: str, page: int, size: int
    ) -> dict:
        async with self.session.begin():
            _, imported = await self.repository.source(owner, dataset_id)
            info = await self._ready()
            require_adapter(info, imported)
            rows, total = await self.repository.companies(dataset_id, keyword, page, size)
            items = []
            for row in rows:
                properties = row.data.get("properties", {})
                items.append(
                    FinancialCompany(
                        recordId=row.node_id or "",
                        companyId=properties.get("company_id", row.node_id),
                        name=row.data.get("name")
                        or properties.get("company_id")
                        or row.node_id
                        or "",
                        observationMonth=properties.get("observation_month"),
                        snapshot=row.snapshot,
                    )
                )
            return {"items": items, "total": total, "page": page, "pageSize": size}

    async def _ready(self) -> FinancialModelInfo:
        status = await self.client.status()
        if not status.ready or status.model is None:
            raise AppError(
                503, status.errorCode or "DECISION_MODEL_UNAVAILABLE", "财务模型未就绪。"
            )
        return status.model

    async def predict_company(
        self, owner: str, key: str, dataset_id: str, record_id: str
    ) -> SavedFinancialPrediction:
        fingerprint = self._fingerprint(
            {"kind": "company", "datasetId": dataset_id, "recordId": record_id}
        )
        async with self.session.begin():
            cached = await self._existing(owner, key, fingerprint)
            if cached is not None:
                return cached
            dataset, imported = await self.repository.source(owner, dataset_id)
            info = await self._ready()
            adapter_id, adapter_version = require_adapter(info, imported)
            row = await self.repository.company(dataset_id, record_id)
            properties = row.data.get("properties", {})
            source = FinancialSource(
                kind="company",
                datasetId=dataset.id,
                recordId=record_id,
                companyId=properties.get("company_id", record_id),
                companyName=row.data.get("name") or properties.get("company_id") or record_id,
                observationMonth=properties.get("observation_month"),
                snapshot=row.snapshot,
                sourceSha256=imported.manifest.get("sourceSha256", imported.sha256),
            )
            remote = await self.client.predict(
                {
                    "adapterId": adapter_id,
                    "adapterVersion": adapter_version,
                    "attributes": row.data["attributes"],
                    "expectedManifestSha256": info.manifestSha256,
                },
                record=True,
            )
            return await self._save(owner, key, fingerprint, source, remote)

    async def predict_input(
        self, owner: str, key: str, document: dict, label: str
    ) -> SavedFinancialPrediction:
        fingerprint = self._fingerprint({"kind": "input", "input": document, "label": label})
        async with self.session.begin():
            cached = await self._existing(owner, key, fingerprint)
            if cached is not None:
                return cached
            info = await self._ready()
            remote = await self.client.predict(
                {"input": document, "expectedManifestSha256": info.manifestSha256}, record=False
            )
            return await self._save(
                owner, key, fingerprint, FinancialSource(kind="input", label=label), remote
            )

    async def _existing(
        self, owner: str, key: str, fingerprint: str
    ) -> SavedFinancialPrediction | None:
        await self.repository.lock_request(owner, key)
        existing = await self.repository.prediction(owner, key=key)
        if existing is None:
            return None
        if existing.request_sha256 != fingerprint:
            raise AppError(409, "DECISION_REQUEST_CONFLICT", "同一请求键不能用于不同的预测输入。")
        return await self._render(existing)

    async def _save(
        self,
        owner: str,
        key: str,
        fingerprint: str,
        source: FinancialSource,
        remote: FinancialModelResult,
    ) -> SavedFinancialPrediction:
        model = await self.repository.model(remote.model)
        row = FinancialPrediction(
            id=str(uuid4()),
            owner_id=owner,
            model_id=model.id,
            dataset_id=source.datasetId,
            request_key=key,
            request_sha256=fingerprint,
            request_id=current_request_id() or "",
            source=source.model_dump(mode="json"),
            input_snapshot=remote.prediction.inputSnapshot,
            input_serialized=json.dumps(
                remote.prediction.inputSnapshot, separators=(",", ":"), allow_nan=False
            ),
            result=FinancialScore.model_validate(remote.prediction.model_dump()).model_dump(
                mode="json"
            ),
        )
        self.session.add(row)
        await self.session.flush()
        logger.info(
            "financial.prediction_saved",
            extra={
                "prediction_id": row.id,
                "model_version": remote.model.modelVersion,
                "request_id": row.request_id,
            },
        )
        return await self._render(row, model)

    async def get(self, owner: str, identity: str) -> SavedFinancialPrediction:
        row = await self.repository.prediction(owner, identity=identity)
        if row is None:
            raise AppError(404, "DECISION_PREDICTION_NOT_FOUND", "预测记录不存在或无权访问。")
        return await self._render(row)

    async def history(self, owner: str, page: int, size: int) -> dict:
        rows, total = await self.repository.history(owner, page, size)
        return {
            "items": [await self._render(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": size,
        }

    async def _render(
        self, row: FinancialPrediction, model: DeployedFinancialModel | None = None
    ) -> SavedFinancialPrediction:
        model = model or await self.session.get(DeployedFinancialModel, row.model_id)
        assert model is not None
        return SavedFinancialPrediction(
            id=row.id,
            model=RegisteredFinancialModel.model_validate(
                {
                    **model.descriptor,
                    "id": model.id,
                    "device": row.result["device"],
                    "dtype": row.result["dtype"],
                }
            ),
            source=FinancialSource.model_validate(row.source),
            result=FinancialScore.model_validate(row.result),
            createdAt=row.created_at,
        )

    @staticmethod
    def _fingerprint(body: dict) -> str:
        try:
            # Input feature order is significant to the frozen prompt serialization.
            return hashlib.sha256(
                json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
        except (ValueError, OverflowError) as error:
            raise AppError(
                422, "DECISION_INPUT_INVALID", "输入包含非法数值。", field="input"
            ) from error
