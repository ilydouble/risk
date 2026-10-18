import hashlib
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.errors import AppError
from risk_api.modules.decision.contracts import FinancialModelInfo
from risk_api.modules.decision.model import DeployedFinancialModel, FinancialPrediction
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport, EnterpriseRecord


class DecisionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_request(self, owner: str, key: str) -> None:
        # Serialize only identical owner/request keys, including concurrent retries.
        digest = hashlib.sha256(f"{owner}:{key}".encode()).digest()
        lock = int.from_bytes(digest[:8], "big", signed=True)
        await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})

    async def model(self, info: FinancialModelInfo) -> DeployedFinancialModel:
        identity = str(uuid5(NAMESPACE_URL, "risk:financial-model:" + info.manifestSha256))
        await self.session.execute(
            insert(DeployedFinancialModel)
            .values(
                id=identity,
                model_version=info.modelVersion,
                manifest_sha256=info.manifestSha256,
                descriptor=info.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=["model_version"])
        )
        result = await self.session.scalar(
            select(DeployedFinancialModel).where(
                DeployedFinancialModel.model_version == info.modelVersion
            )
        )
        if result is None or result.manifest_sha256 != info.manifestSha256:
            raise AppError(
                409, "DECISION_VERSION_CONFLICT", "同名模型版本的内容已改变，须使用新版本。"
            )
        return result

    async def prediction(
        self, owner: str, identity: str | None = None, key: str | None = None
    ) -> FinancialPrediction | None:
        query = select(FinancialPrediction).where(FinancialPrediction.owner_id == owner)
        if identity is not None:
            query = query.where(FinancialPrediction.id == identity)
        if key is not None:
            query = query.where(FinancialPrediction.request_key == key)
        return await self.session.scalar(query)

    async def source(self, owner: str, dataset_id: str) -> tuple[Dataset, EnterpriseImport]:
        dataset = await ModelingRepository(self.session).dataset(owner, dataset_id)
        imported = await self.session.get(EnterpriseImport, dataset_id)
        if imported is None:
            raise AppError(409, "DECISION_DATA_NOT_READY", "请先完成数据集校验和企业导入。")
        return dataset, imported

    async def company(self, dataset_id: str, record_id: str) -> EnterpriseRecord:
        record = await self.session.scalar(
            select(EnterpriseRecord).where(
                EnterpriseRecord.dataset_id == dataset_id,
                EnterpriseRecord.kind == "company",
                EnterpriseRecord.node_id == record_id,
            )
        )
        if record is None:
            raise AppError(
                404, "DECISION_RECORD_NOT_FOUND", "企业观测记录不存在。", field="recordId"
            )
        return record

    async def datasets(self, owner: str) -> list[tuple[Dataset, EnterpriseImport]]:
        rows = await self.session.execute(
            select(Dataset, EnterpriseImport)
            .join(EnterpriseImport, EnterpriseImport.dataset_id == Dataset.id)
            .where(Dataset.owner_id == owner, Dataset.protocol_generation == 2)
            .order_by(Dataset.created_at.desc(), Dataset.id)
            .limit(100)
        )
        return [(row[0], row[1]) for row in rows]

    async def companies(
        self, dataset_id: str, keyword: str, page: int, size: int
    ) -> tuple[list[EnterpriseRecord], int]:
        record = EnterpriseRecord
        condition = (record.dataset_id == dataset_id) & (record.kind == "company")
        if keyword:
            exact = condition & or_(
                record.node_id == keyword,
                record.data.op("->")("properties").op("->>")("company_id") == keyword,
            )
            # Resolve authoritative IDs first. Prefix names use a small expression index;
            # scanning every toasted financial payload can exceed the gateway timeout.
            matches = await self.session.scalar(
                select(func.count()).select_from(record).where(exact)
            )
            condition = exact if matches else condition & func.lower(
                record.data["name"].astext
            ).startswith(keyword.lower(), autoescape=True)
        total = await self.session.scalar(select(func.count()).select_from(record).where(condition))
        rows = await self.session.scalars(
            select(record)
            .where(condition)
            .order_by(record.node_id, record.sequence)
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows), total or 0

    async def history(
        self, owner: str, page: int, size: int
    ) -> tuple[list[FinancialPrediction], int]:
        condition = FinancialPrediction.owner_id == owner
        total = await self.session.scalar(
            select(func.count()).select_from(FinancialPrediction).where(condition)
        )
        rows = await self.session.scalars(
            select(FinancialPrediction)
            .where(condition)
            .order_by(FinancialPrediction.created_at.desc(), FinancialPrediction.id)
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows), total or 0
