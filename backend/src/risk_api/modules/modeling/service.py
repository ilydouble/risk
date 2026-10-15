from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from stellarmesh_objectstorage import AsyncClient, StorageError

from risk_api.errors import AppError
from risk_api.modules.data_prep.model import Preparation
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.workbench_model import (
    Dataset,
    Dispatch,
    EnterprisePrediction,
    ModelVersion,
    Run,
)


@dataclass
class ModelingStorage:
    client: AsyncClient


class ModelingService:
    def __init__(
        self, repository: ModelingRepository, storage: ModelingStorage, client: ModelClient
    ):
        self.repository, self.storage, self.client = repository, storage.client, client
        self.session = repository.session

    async def refresh(self, item: Dataset | Run) -> None:
        if isinstance(item, Dataset) and not item.confirmed:
            return
        if item.execution.get("status") in {"completed", "failed", "cancelled"}:
            return
        try:
            snapshot = await self.client.call("jobs/get", {"jobId": item.id})
        except AppError as error:
            if error.code == "MODEL_RESOURCE_NOT_FOUND":
                return  # Transactional outbox is still delivering the initial submission.
            raise
        item.execution = snapshot
        await self.session.commit()

    def enqueue(self, identity: str, kind: str, payload: dict, request_id: str) -> None:
        self.session.add(
            Dispatch(
                id=identity,
                operation="submit",
                request_id=request_id,
                payload={"jobId": identity, "kind": kind, "payload": payload},
            )
        )

    async def create_upload(
        self, owner: str, name: str, filename: str, content_type: str, size: int,
        source_preparation_id: str | None = None,
    ) -> dict[str, Any]:
        filename = PurePath(filename.replace("\\", "/")).name
        if not filename.lower().endswith(".zip") or not name.strip():
            raise AppError(422, "MODELING_FILE_INVALID", "A named ZIP dataset is required")
        mapping_snapshot: dict = {}
        if source_preparation_id:
            source = await self.session.scalar(select(Preparation).where(
                Preparation.id == source_preparation_id, Preparation.owner_id == owner,
            ).with_for_update())
            if source is None or not source.confirmed or not source.in_workbench:
                raise AppError(409, "MODELING_STATE_INVALID", "请先确认并移交当前账号的映射方案")
            mapping_snapshot = {
                "sourceSha256": source.source_sha, "mapping": deepcopy(source.mapping),
                "sourceUpdatedAt": source.updated_at.isoformat(),
                "capturedAt": datetime.now(UTC).isoformat(),
            }
        identity = str(uuid4())
        key = f"uploads/{owner}/{identity}.zip"
        try:
            ticket = await self.storage.presign_put(
                key, size=size, content_type=content_type, expires_in=60
            )
        except StorageError as error:
            raise AppError(
                503, "MODELING_STORAGE_UNAVAILABLE", "Object storage unavailable"
            ) from error
        self.session.add(
            Dataset(
                id=identity,
                owner_id=owner,
                name=name.strip(),
                filename=filename,
                object_key=key,
                content_type=content_type,
                size=size,
                source_preparation_id=source_preparation_id, mapping_snapshot=mapping_snapshot,
            )
        )
        await self.session.commit()
        return {
            "datasetId": identity,
            "url": ticket.url,
            "headers": ticket.headers,
            "expiresIn": 60,
        }

    async def complete_upload(self, owner: str, identity: str, request_id: str) -> Dataset:
        dataset = await self.repository.dataset(owner, identity, lock=True)
        if not dataset.confirmed:
            try:
                info = await self.storage.stat(dataset.object_key)
            except StorageError as error:
                raise AppError(
                    409, "MODELING_UPLOAD_INCOMPLETE", "Upload is not complete"
                ) from error
            if info.size != dataset.size:
                raise AppError(409, "MODELING_UPLOAD_INCOMPLETE", "Uploaded size differs")
            dataset.confirmed = True
            self.enqueue(dataset.id, "validate", {"objectKey": dataset.object_key}, request_id)
            await self.session.commit()
        return dataset

    async def get_dataset(self, owner: str, identity: str) -> Dataset:
        item = await self.repository.dataset(owner, identity)
        await self.refresh(item)
        return item

    async def get_run(self, owner: str, identity: str) -> Run:
        item = await self.repository.run(owner, identity)
        await self.refresh(item)
        return item

    async def capabilities(self) -> dict[str, Any]:
        return await self.client.call("models/capabilities", {})

    async def run_configuration(
        self,
        owner: str,
        dataset_id: str,
        parameters: dict,
        request_id: str,
        expected_digest: str | None = None,
    ) -> dict[str, Any]:
        source = await self.get_dataset(owner, dataset_id)
        if source.execution.get("status") != "completed":
            raise AppError(409, "MODELING_DATASET_NOT_READY", "Dataset is not ready")
        if "riskgnn" not in source.execution.get("result", {}).get("supportedRunnerIds", []):
            raise AppError(422, "MODELING_MODEL_INCOMPATIBLE", "Model cannot train this dataset")
        return await self.client.call(
            "models/configuration",
            {
                "jobId": dataset_id,
                "parameters": parameters,
                "expectedDigest": expected_digest,
            },
            request_id,
        )

    async def create_run(
        self,
        owner: str,
        dataset_id: str,
        name: str,
        request_key: str,
        parameters: dict,
        request_id: str,
        retry_of: str | None = None,
        *,
        runner_id: str = "riskgnn",
        configuration_digest: str | None = None,
        frozen_configuration: dict | None = None,
    ) -> Run:
        previous = await self.session.scalar(
            select(Run).where(
                Run.owner_id == owner, Run.request_key == request_key, Run.protocol_generation == 2
            )
        )
        if previous:
            if (
                previous.dataset_id,
                previous.name,
                previous.configuration.get("runnerId", "riskgnn"),
                previous.configuration.get(
                    "requestedParameters",
                    {
                        "epochs": previous.configuration.get("epochs", 2),
                    },
                ),
                previous.retry_of,
            ) != (
                dataset_id,
                name,
                runner_id,
                parameters,
                retry_of,
            ):
                raise AppError(
                    409, "MODELING_STATE_INVALID", "Request key reused with different input"
                )
            if (
                configuration_digest is not None
                and previous.configuration.get("schemaDigest") != configuration_digest
            ):
                raise AppError(409, "MODELING_STATE_INVALID", "Request key reused with new schema")
            return previous
        source = await self.get_dataset(owner, dataset_id)
        if source.execution.get("status") != "completed":
            raise AppError(409, "MODELING_DATASET_NOT_READY", "Dataset is not ready")
        result = source.execution.get("result", {})
        supported = result.get("supportedRunnerIds", [])
        if runner_id not in supported:
            raise AppError(422, "MODELING_MODEL_INCOMPATIBLE", "Model cannot train this dataset")
        # Resolve before committing; the run and its outbox carry the same immutable snapshot.
        configuration = (
            deepcopy(frozen_configuration)
            if frozen_configuration
            else (
                await self.run_configuration(
                    owner, dataset_id, parameters, request_id, configuration_digest
                )
            )
        )
        config = {"runnerId": runner_id, **configuration}
        item = Run(
            id=str(uuid4()),
            owner_id=owner,
            dataset_id=dataset_id,
            name=name,
            request_key=request_key,
            configuration=config,
            retry_of=retry_of,
        )
        self.session.add(item)
        self.enqueue(
            item.id,
            "train",
            {"sourceJobId": dataset_id, "configuration": configuration, "runnerId": runner_id},
            request_id,
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(Run).where(
                    Run.owner_id == owner,
                    Run.request_key == request_key,
                    Run.protocol_generation == 2,
                )
            )
            if existing is None:
                raise
            return await self.create_run(
                owner,
                dataset_id,
                name,
                request_key,
                parameters,
                request_id,
                retry_of,
                runner_id=runner_id,
                configuration_digest=configuration_digest,
                frozen_configuration=frozen_configuration,
            )
        return item

    async def rerun(self, owner: str, identity: str, key: str, request_id: str) -> Run:
        previous = await self.get_run(owner, identity)
        if previous.configuration.get("resolvedParameters", {}).get("algorithm") != "riskgnn-plus":
            raise AppError(
                409, "MODELING_CONFIG_STALE", "Create a new RiskGNN+ experiment for this dataset"
            )
        if previous.execution.get("status") not in {"failed", "completed", "cancelled"}:
            raise AppError(409, "MODELING_STATE_INVALID", "Run is still active")
        configuration = None
        if "resolvedParameters" in previous.configuration:
            configuration = deepcopy(previous.configuration)
            configuration.pop("runnerId", None)
            # Rerunning explicitly requests the original final values, never today's defaults.
            configuration["requestedParameters"] = deepcopy(configuration["resolvedParameters"])
            parameters = configuration["resolvedParameters"]
        else:
            # Legacy runs have no snapshot. Their immutable ZIP still supplies dataset defaults.
            parameters = {"epochs": previous.configuration["epochs"]}
        return await self.create_run(
            owner,
            previous.dataset_id,
            previous.name,
            key,
            parameters,
            request_id,
            previous.id,
            runner_id=previous.configuration.get("runnerId", "riskgnn"),
            frozen_configuration=configuration,
        )

    async def cancel(self, owner: str, identity: str, request_id: str) -> Run:
        item = await self.repository.run(owner, identity, lock=True)
        if item.execution.get("status") not in {"completed", "failed", "cancelled"}:
            self.session.add(
                Dispatch(
                    id=str(uuid4()),
                    operation="cancel",
                    payload={"jobId": item.id},
                    request_id=request_id,
                )
            )
            item.execution = {**item.execution, "cancelRequested": True}
            await self.session.commit()
        return item

    async def events(self, owner: str, identity: str, after: int) -> dict:
        await self.repository.run(owner, identity)
        try:
            return await self.client.call("jobs/events", {"jobId": identity, "after": after})
        except AppError as error:
            if error.code == "MODEL_RESOURCE_NOT_FOUND":
                return {"items": []}
            raise

    async def publish(self, owner: str, identity: str, name: str) -> ModelVersion:
        run = await self.get_run(owner, identity)
        # The locked run makes concurrent publication a single immutable model version.
        run = await self.repository.run(owner, identity, lock=True)
        previous = await self.session.scalar(
            select(ModelVersion).where(ModelVersion.run_id == identity)
        )
        if previous:
            return previous
        result = run.execution.get("result", {})
        if (
            run.execution.get("status") != "completed"
            or not result.get("report", {}).get("independentReload")
            or not result.get("sha256")
        ):
            raise AppError(
                409, "MODELING_STATE_INVALID", "Independent test must complete before publication"
            )
        version = ModelVersion(
            id=str(uuid4()), owner_id=owner, run_id=identity, name=name, artifact=result
        )
        self.session.add(version)
        await self.session.commit()
        return version

    async def download(self, owner: str, identity: str) -> dict:
        version = await self.repository.version(owner, identity)
        ticket = await self.storage.presign_get(version.artifact["objectKey"], expires_in=60)
        return {"url": ticket.url, "sha256": version.artifact["sha256"], "expiresIn": 60}

    async def predict(self, owner: str, identity: str, ids: list[str], request_id: str) -> dict:
        version = await self.repository.version(owner, identity)
        result = await self.client.call(
            "models/predict", {"jobId": version.run_id, "companyIds": ids}, request_id
        )
        run = await self.repository.run(owner, version.run_id)
        for prediction in result["items"]:
            statement = insert(EnterprisePrediction).values(
                model_id=identity,
                company_id=prediction["companyId"],
                dataset_id=run.dataset_id,
                result=prediction,
            )
            await self.session.execute(statement.on_conflict_do_nothing())
        await self.session.commit()
        return result
