import logging
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any
from uuid import uuid4

from stellarmesh_objectstorage import AsyncClient, NotFoundError, StorageError

from risk_api.modules.modeling.errors import ModelingError
from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment, ModelingJob
from risk_api.modules.modeling.repository import ModelingRepository

logger = logging.getLogger(__name__)

MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MODEL_NAMES = {
    "logistic_regression",
    "hist_gradient_boosting",
    "graph_stats_hgb",
    "gnn_self_only",
    "gnn_no_hyper",
    "gnn_full",
}


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
        if filename in {"", ".", ".."} or not filename.casefold().endswith(".zip"):
            raise ModelingError("FILE_INVALID", field="filename")
        if size <= 0 or size > MAX_BUNDLE_BYTES:
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
            status="pending_upload",
            schema_version=1,
            capabilities={},
            validation={},
            progress={"stage": "upload", "percent": 0},
        )
        await self.repository.add_dataset(dataset)
        return DatasetUploadTicket(dataset_id, signed.url, dict(signed.headers))

    async def complete_upload(self, owner_id: str, dataset_id: str) -> ModelingDataset:
        dataset = await self.get_dataset(owner_id, dataset_id)
        if dataset.status in {"queued", "running", "ready"}:
            return dataset
        if dataset.status == "failed":
            raise ModelingError("DATASET_NOT_READY")
        try:
            info = await self.storage.stat(dataset.object_key)
        except NotFoundError as error:
            raise ModelingError("UPLOAD_INCOMPLETE") from error
        except StorageError as error:
            raise ModelingError("STORAGE_UNAVAILABLE") from error
        if info.size != dataset.size or info.size > MAX_BUNDLE_BYTES:
            raise ModelingError("FILE_INVALID", field="size")
        dataset.status = "queued"
        dataset.progress = {"stage": "queued", "percent": 0}
        dataset.error = None
        await self.repository.add_job(
            ModelingJob(
                id=str(uuid4()),
                owner_id=owner_id,
                dataset_id=dataset.id,
                kind="analyze_bundle",
                status="queued",
                payload={"objectKey": dataset.object_key},
                progress={"stage": "queued", "percent": 0},
            )
        )
        await self.repository.save_dataset(dataset)
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
        target_name: str,
        feature_mode: str,
        feature_columns: list[str],
        models: list[str],
        use_events: bool,
        use_relations: bool,
        use_hyperedges: bool,
        enable_gnn_ablations: bool,
        seed: int,
    ) -> ModelingExperiment:
        name = name.strip()
        if not name:
            raise ModelingError("CONFIGURATION_INVALID", field="name")
        dataset = await self.get_dataset(owner_id, dataset_id)
        if dataset.status != "ready":
            raise ModelingError("DATASET_NOT_READY")
        if dataset.schema_version != 1 or dataset.manifest is None:
            raise ModelingError("CONFIGURATION_INVALID", field="datasetId")
        target = dataset.manifest.get("target", {})
        if target_name != target.get("name"):
            raise ModelingError("CONFIGURATION_INVALID", field="targetName")
        requested_models = list(dict.fromkeys(models))
        if not requested_models or not set(requested_models).issubset(MODEL_NAMES):
            raise ModelingError("CONFIGURATION_INVALID", field="models")
        features = {item["name"] for item in dataset.manifest.get("features", [])}
        if feature_mode == "manual":
            if not feature_columns or not set(feature_columns).issubset(features):
                raise ModelingError("CONFIGURATION_INVALID", field="featureColumns")
        elif feature_mode != "recommended":
            raise ModelingError("CONFIGURATION_INVALID", field="featureMode")
        self._validate_capabilities(dataset.capabilities, requested_models)
        if not use_relations and any(
            model in {"graph_stats_hgb", "gnn_no_hyper", "gnn_full"}
            for model in requested_models
        ):
            raise ModelingError("CONFIGURATION_INVALID", field="useRelations")
        if "gnn_full" in requested_models and not use_hyperedges:
            raise ModelingError("CONFIGURATION_INVALID", field="useHyperedges")
        configuration: dict[str, Any] = {
            "seed": seed,
            "featureMode": feature_mode,
            "useEvents": use_events,
            "useRelations": use_relations,
            "useHyperedges": use_hyperedges,
            "enableGnnAblations": enable_gnn_ablations,
        }
        experiment = ModelingExperiment(
            id=str(uuid4()),
            dataset_id=dataset_id,
            owner_id=owner_id,
            name=name,
            model_type="comparison_suite",
            status="queued",
            target_column="target",
            positive_value=str(target.get("positiveValue", "1")),
            feature_columns=feature_columns,
            configuration=configuration,
            metrics={},
            coefficients=[],
            target_name=target_name,
            selected_features=[],
            requested_models=requested_models,
            progress={"stage": "queued", "percent": 0},
            results={},
            artifacts={},
        )
        await self.repository.add_experiment(experiment)
        await self.repository.add_job(
            ModelingJob(
                id=str(uuid4()),
                owner_id=owner_id,
                dataset_id=dataset_id,
                experiment_id=experiment.id,
                kind="train_experiment",
                status="queued",
                payload={"objectKey": dataset.object_key},
                progress={"stage": "queued", "percent": 0},
            )
        )
        return experiment

    @staticmethod
    def _validate_capabilities(capabilities: dict[str, Any], models: list[str]) -> None:
        if "graph_stats_hgb" in models and not capabilities.get("relations"):
            raise ModelingError("CONFIGURATION_INVALID", field="models")
        if any(model.startswith("gnn_") for model in models) and not capabilities.get("gnn"):
            raise ModelingError("CONFIGURATION_INVALID", field="models")
        if "gnn_full" in models and not capabilities.get("hyperedges"):
            raise ModelingError("CONFIGURATION_INVALID", field="models")

    async def get_experiment(self, owner_id: str, experiment_id: str) -> ModelingExperiment:
        experiment = await self.repository.experiment(experiment_id, owner_id)
        if experiment is None:
            raise ModelingError("EXPERIMENT_NOT_FOUND")
        return experiment

    async def list_experiments(self, owner_id: str) -> list[ModelingExperiment]:
        return await self.repository.experiments(owner_id)
