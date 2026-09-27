import asyncio
import logging
from dataclasses import dataclass
from pathlib import PurePath
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient, NotFoundError, StorageError

from risk_api.modules.modeling.analysis import AnalysisError, analyze_csv, train_baseline
from risk_api.modules.modeling.errors import ModelingError
from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment
from risk_api.modules.modeling.repository import ModelingRepository

logger = logging.getLogger(__name__)

MAX_DATASET_BYTES = 5_000_000


@dataclass(frozen=True)
class DatasetUploadTicket:
    dataset_id: str
    url: str
    headers: dict[str, str]


class ModelingService:
    def __init__(self, repository: ModelingRepository, storage: AsyncClient):
        self.repository = repository
        self.storage = storage

    async def create_upload(
        self,
        owner_id: str,
        name: str,
        filename: str,
        content_type: str,
        size: int,
    ) -> DatasetUploadTicket:
        name = name.strip()
        if not name:
            raise ModelingError("FILE_INVALID", field="name")
        filename = PurePath(filename.replace("\\", "/")).name
        if filename in {"", ".", ".."} or not filename.casefold().endswith(".csv"):
            raise ModelingError("FILE_INVALID", field="filename")
        if size > MAX_DATASET_BYTES:
            raise ModelingError("FILE_INVALID", field="size")
        dataset_id = str(uuid4())
        key = f"modeling/{owner_id}/{dataset_id}/{filename}"
        try:
            signed = await self.storage.presign_put(
                key, size=size, content_type=content_type, expires_in=60
            )
        except StorageError as error:
            raise ModelingError("STORAGE_UNAVAILABLE") from error
        dataset = ModelingDataset(
            id=dataset_id,
            owner_id=owner_id,
            name=name,
            object_key=key,
            filename=filename,
            content_type=content_type,
            size=size,
            status="pending",
        )
        await self.repository.add_dataset(dataset)
        logger.info(
            "modeling.dataset_upload_requested",
            extra={"dataset_id": dataset_id, "owner_id": owner_id, "size_bytes": size},
        )
        return DatasetUploadTicket(dataset_id, signed.url, dict(signed.headers))

    async def complete_upload(self, owner_id: str, dataset_id: str) -> ModelingDataset:
        dataset = await self.get_dataset(owner_id, dataset_id)
        if dataset.status == "ready":
            return dataset
        try:
            info = await self.storage.stat(dataset.object_key)
        except NotFoundError as error:
            raise ModelingError("UPLOAD_INCOMPLETE") from error
        except StorageError as error:
            raise ModelingError("STORAGE_UNAVAILABLE") from error
        if info.size != dataset.size or info.size > MAX_DATASET_BYTES:
            raise ModelingError("FILE_INVALID", field="size")
        payload = await self._read(dataset.object_key)
        try:
            analysis, preview = await asyncio.to_thread(analyze_csv, payload)
        except AnalysisError as error:
            dataset.status = "failed"
            dataset.error = str(error)
            await self.repository.save_dataset(dataset)
            raise ModelingError("FILE_INVALID") from error
        dataset.status = "ready"
        dataset.row_count = analysis["rowCount"]
        dataset.column_count = analysis["columnCount"]
        dataset.analysis = analysis
        dataset.preview = preview
        dataset.error = None
        await self.repository.save_dataset(dataset)
        logger.info(
            "modeling.dataset_analyzed",
            extra={
                "dataset_id": dataset.id,
                "owner_id": owner_id,
                "row_count": dataset.row_count,
                "column_count": dataset.column_count,
            },
        )
        return dataset

    async def get_dataset(self, owner_id: str, dataset_id: str) -> ModelingDataset:
        dataset = await self.repository.dataset(dataset_id, owner_id)
        if dataset is None:
            raise ModelingError("DATASET_NOT_FOUND")
        return dataset

    async def list_datasets(self, owner_id: str) -> list[ModelingDataset]:
        return await self.repository.datasets(owner_id)

    async def run_experiment(
        self,
        owner_id: str,
        dataset_id: str,
        name: str,
        target_column: str,
        positive_value: str,
        feature_columns: list[str],
        seed: int,
    ) -> ModelingExperiment:
        name = name.strip()
        if not name:
            raise ModelingError("CONFIGURATION_INVALID", field="name")
        dataset = await self.get_dataset(owner_id, dataset_id)
        if dataset.status != "ready":
            raise ModelingError("DATASET_NOT_READY")
        payload = await self._read(dataset.object_key)
        try:
            result = await asyncio.to_thread(
                train_baseline,
                payload,
                target_column,
                positive_value,
                feature_columns,
                seed,
            )
        except AnalysisError as error:
            raise ModelingError("CONFIGURATION_INVALID") from error
        experiment = ModelingExperiment(
            id=str(uuid4()),
            dataset_id=dataset_id,
            owner_id=owner_id,
            name=name,
            model_type="logistic_regression",
            status="completed",
            target_column=target_column,
            positive_value=positive_value,
            feature_columns=feature_columns,
            configuration=result["configuration"],
            metrics=result["metrics"],
            coefficients=result["coefficients"],
        )
        await self.repository.add_experiment(experiment)
        logger.info(
            "modeling.experiment_completed",
            extra={
                "dataset_id": dataset_id,
                "experiment_id": experiment.id,
                "owner_id": owner_id,
                "feature_count": len(feature_columns),
            },
        )
        return experiment

    async def get_experiment(self, owner_id: str, experiment_id: str) -> ModelingExperiment:
        experiment = await self.repository.experiment(experiment_id, owner_id)
        if experiment is None:
            raise ModelingError("EXPERIMENT_NOT_FOUND")
        return experiment

    async def list_experiments(self, owner_id: str) -> list[ModelingExperiment]:
        return await self.repository.experiments(owner_id)

    async def _read(self, object_key: str) -> bytes:
        try:
            async with self.storage.open_object(object_key) as stream:
                payload = await stream.read(MAX_DATASET_BYTES + 1)
        except NotFoundError as error:
            raise ModelingError("UPLOAD_INCOMPLETE") from error
        except StorageError as error:
            raise ModelingError("STORAGE_UNAVAILABLE") from error
        if len(payload) > MAX_DATASET_BYTES:
            raise ModelingError("FILE_INVALID", field="size")
        return payload
