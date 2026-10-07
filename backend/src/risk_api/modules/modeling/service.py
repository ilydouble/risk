from dataclasses import dataclass
from pathlib import PurePath
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from stellarmesh_objectstorage import AsyncClient, StorageError

from risk_api.errors import AppError
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.workbench_model import Dataset, Dispatch, ModelVersion, Run


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
        self, owner: str, name: str, filename: str, content_type: str, size: int
    ) -> dict[str, Any]:
        filename = PurePath(filename.replace("\\", "/")).name
        if not filename.lower().endswith(".zip") or not name.strip():
            raise AppError(422, "MODELING_FILE_INVALID", "A named ZIP dataset is required")
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

    async def create_run(
        self,
        owner: str,
        dataset_id: str,
        name: str,
        request_key: str,
        epochs: int,
        request_id: str,
        retry_of: str | None = None,
        *,
        runner_id: str = "riskgnn-node-edge",
    ) -> Run:
        config = {"profile": "smoke-v1", "epochs": epochs, "seed": 0, "runnerId": runner_id}
        previous = await self.session.scalar(
            select(Run).where(Run.owner_id == owner, Run.request_key == request_key)
        )
        if previous:
            if (
                previous.dataset_id,
                previous.name,
                {"runnerId": "riskgnn-node-edge", **previous.configuration},
                previous.retry_of,
            ) != (
                dataset_id,
                name,
                config,
                retry_of,
            ):
                raise AppError(
                    409, "MODELING_STATE_INVALID", "Request key reused with different input"
                )
            return previous
        source = await self.get_dataset(owner, dataset_id)
        if source.execution.get("status") != "completed":
            raise AppError(409, "MODELING_DATASET_NOT_READY", "Dataset is not ready")
        result = source.execution.get("result", {})
        supported = result.get("supportedRunnerIds", ["riskgnn-node-edge"])
        if runner_id not in supported:
            raise AppError(422, "MODELING_MODEL_INCOMPATIBLE", "Model cannot train this dataset")
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
            {"sourceJobId": dataset_id, "epochs": epochs, "runnerId": runner_id},
            request_id,
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(Run).where(Run.owner_id == owner, Run.request_key == request_key)
            )
            if existing is None:
                raise
            return await self.create_run(
                owner,
                dataset_id,
                name,
                request_key,
                epochs,
                request_id,
                retry_of,
                runner_id=runner_id,
            )
        return item

    async def rerun(self, owner: str, identity: str, key: str, request_id: str) -> Run:
        previous = await self.get_run(owner, identity)
        if previous.execution.get("status") not in {"failed", "completed", "cancelled"}:
            raise AppError(409, "MODELING_STATE_INVALID", "Run is still active")
        return await self.create_run(
            owner,
            previous.dataset_id,
            previous.name,
            key,
            previous.configuration["epochs"],
            request_id,
            previous.id,
            runner_id=previous.configuration.get("runnerId", "riskgnn-node-edge"),
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
        return await self.client.call(
            "models/predict", {"jobId": version.run_id, "companyIds": ids}, request_id
        )
