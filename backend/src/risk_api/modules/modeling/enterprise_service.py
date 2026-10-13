"""Atomic enterprise import and owner-scoped reads of adapter-owned data."""

import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import func, insert, or_, select, text
from sqlalchemy.exc import IntegrityError
from stellarmesh_objectstorage import StorageError

from risk_api.errors import AppError
from risk_api.modules.modeling.enterprise_data import FORMAT, MAX_BYTES, records
from risk_api.modules.modeling.workbench_model import (
    EnterpriseImport,
    EnterprisePrediction,
    EnterpriseRecord,
)


class EnterpriseService:
    def __init__(self, modeling):
        self.modeling = modeling
        self.session = modeling.session
        self.repository = modeling.repository

    async def import_dataset(self, owner: str, identity: str) -> EnterpriseImport:
        source = await self.modeling.get_dataset(owner, identity)
        if source.execution.get("status") != "completed":
            raise AppError(409, "MODELING_DATASET_NOT_READY", "Dataset is not ready")
        result = source.execution.get("result", {})
        artifact = result.get("enterpriseArtifact") or {}
        if artifact.get("format") != FORMAT or artifact.get("kind") != "file":
            raise AppError(
                409, "MODELING_ENTERPRISE_UNAVAILABLE", "Re-upload to export enterprise data"
            )
        if not 0 < artifact.get("size", 0) <= MAX_BYTES:
            raise AppError(422, "MODELING_ENTERPRISE_INVALID", "Enterprise artifact exceeds limit")
        existing = await self.session.get(EnterpriseImport, identity)
        if existing:
            if existing.sha256 != artifact["sha256"]:
                raise AppError(409, "MODELING_STATE_INVALID", "Imported dataset changed")
            return existing
        try:
            with TemporaryDirectory(prefix="risk-enterprises-") as directory:
                path = Path(directory) / "data.jsonl"
                sha, size = hashlib.sha256(), 0
                async with self.modeling.storage.open_object(artifact["objectKey"]) as stream:
                    with path.open("wb") as output:
                        async for chunk in stream.iter_chunks():
                            size += len(chunk)
                            if size > MAX_BYTES or size > artifact["size"]:
                                raise ValueError("Enterprise artifact exceeds declared size")
                            sha.update(chunk)
                            await asyncio.to_thread(output.write, chunk)
                if size != artifact["size"] or sha.hexdigest() != artifact["sha256"]:
                    raise ValueError("Enterprise artifact checksum mismatch")
                # Serialize imports of the same dataset; all inserts commit together.
                await self.repository.dataset(owner, identity, lock=True)
                existing = await self.session.get(EnterpriseImport, identity)
                if existing:
                    return existing
                iterator = records(path)
                _, manifest = next(iterator)
                if (
                    manifest["datasetContract"] != result["datasetContract"]
                    or manifest["sourceSha256"] != result["sha256"]
                ):
                    raise ValueError("Enterprise data belongs to a different source")
                item = EnterpriseImport(
                    dataset_id=identity, sha256=artifact["sha256"], manifest=manifest, counts={}
                )
                self.session.add(item)
                await self.session.flush()
                counts: dict[str, int] = {}
                batch = []
                for sequence, record in iterator:
                    counts[record.kind] = counts.get(record.kind, 0) + 1
                    batch.append(
                        {
                            "dataset_id": identity,
                            "sequence": sequence,
                            "kind": record.kind,
                            "snapshot": record.snapshot,
                            "node_id": record.nodeId,
                            "source": record.source,
                            "target": record.target,
                            "members": record.members,
                            "data": record.data,
                        }
                    )
                    if len(batch) == 500:
                        await self.session.execute(insert(EnterpriseRecord), batch)
                        batch = []
                if batch:
                    await self.session.execute(insert(EnterpriseRecord), batch)
                if counts != result["enterpriseData"]["counts"]:
                    raise ValueError("Enterprise record counts differ")
                await self.verify_references(identity)
                item.counts = counts
                await self.session.commit()
                return item
        except StorageError as error:
            await self.session.rollback()
            raise AppError(
                503, "MODELING_STORAGE_UNAVAILABLE", "Object storage unavailable"
            ) from error
        except (ValueError, KeyError, IntegrityError) as error:
            await self.session.rollback()
            raise AppError(422, "MODELING_ENTERPRISE_INVALID", "Invalid enterprise data") from error

    async def verify_references(self, identity: str) -> None:
        # Every reference resolves within its own snapshot, including repeated person IDs.
        invalid = await self.session.scalar(
            text("""
            WITH refs AS (
                SELECT dataset_id,snapshot,source AS id,kind='event' AS company_only
                  FROM workbench_enterprise_records
                  WHERE dataset_id=:dataset AND source IS NOT NULL
                UNION ALL
                SELECT dataset_id,snapshot,target,false FROM workbench_enterprise_records
                  WHERE dataset_id=:dataset AND target IS NOT NULL
                UNION ALL
                SELECT dataset_id,snapshot,jsonb_array_elements_text(members),true
                  FROM workbench_enterprise_records WHERE dataset_id=:dataset
            ) SELECT 1 FROM refs r LEFT JOIN workbench_enterprise_records n
              ON n.dataset_id=r.dataset_id AND n.snapshot=r.snapshot AND n.node_id=r.id
              WHERE n.node_id IS NULL OR (r.company_only AND n.kind!='company') LIMIT 1
        """),
            {"dataset": identity},
        )
        if invalid:
            raise ValueError("Unresolved enterprise relation")

    async def page(
        self,
        owner: str,
        identity: str,
        kind: str,
        keyword: str,
        node: str | None,
        snapshot: str | None,
        model: str | None,
        page: int,
        size: int,
    ) -> dict:
        await self.repository.dataset(owner, identity)
        imported = await self.session.get(EnterpriseImport, identity)
        if imported is None:
            return {"imported": False, "items": [], "total": 0, "counts": {}, "manifest": {}}
        if model:
            version = await self.repository.version(owner, model)
            run = await self.repository.run(owner, version.run_id)
            if run.dataset_id != identity:
                raise AppError(409, "MODELING_STATE_INVALID", "Model belongs to another dataset")
        record = EnterpriseRecord
        conditions = [record.dataset_id == identity, record.kind == kind]
        if keyword:
            conditions.append(
                or_(
                    record.node_id.icontains(keyword, autoescape=True),
                    record.data["name"].astext.icontains(keyword, autoescape=True),
                )
            )
        if snapshot:
            conditions.append(record.snapshot == snapshot)
        if node:
            conditions.append(
                or_(
                    record.node_id == node,
                    record.source == node,
                    record.target == node,
                    record.members.contains([node]),
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(record).where(*conditions)
        )
        rows = list(
            await self.session.scalars(
                select(record)
                .where(*conditions)
                .order_by(record.sequence)
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        predictions = {}
        if model:
            predictions = {
                p.company_id: p.result
                for p in await self.session.scalars(
                    select(EnterprisePrediction).where(
                        EnterprisePrediction.model_id == model,
                        EnterprisePrediction.company_id.in_([r.node_id for r in rows if r.node_id]),
                    )
                )
            }
        return {
            "imported": True,
            "total": total or 0,
            "counts": imported.counts,
            "manifest": imported.manifest,
            "items": [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "snapshot": r.snapshot,
                    "nodeId": r.node_id,
                    "source": r.source,
                    "target": r.target,
                    "members": r.members,
                    "data": r.data,
                    "prediction": predictions.get(r.node_id),
                }
                for r in rows
            ],
        }
