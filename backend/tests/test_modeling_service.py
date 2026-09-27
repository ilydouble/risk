import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from risk_api.modules.modeling.errors import ModelingError
from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment, ModelingJob
from risk_api.modules.modeling.service import ModelingService


class FakeRepository:
    def __init__(self) -> None:
        self.dataset_rows: dict[str, ModelingDataset] = {}
        self.experiment_rows: dict[str, ModelingExperiment] = {}
        self.job_rows: dict[str, ModelingJob] = {}

    async def add_dataset(self, dataset: ModelingDataset) -> None:
        self.dataset_rows[dataset.id] = dataset

    async def dataset(self, dataset_id: str, owner_id: str) -> ModelingDataset | None:
        dataset = self.dataset_rows.get(dataset_id)
        return dataset if dataset and dataset.owner_id == owner_id else None

    async def datasets(self, owner_id: str) -> list[ModelingDataset]:
        return [row for row in self.dataset_rows.values() if row.owner_id == owner_id]

    async def save_dataset(self, dataset: ModelingDataset) -> None:
        self.dataset_rows[dataset.id] = dataset

    async def add_experiment(self, experiment: ModelingExperiment) -> None:
        self.experiment_rows[experiment.id] = experiment

    async def add_job(self, job: ModelingJob) -> None:
        self.job_rows[job.id] = job

    async def experiment(
        self, experiment_id: str, owner_id: str
    ) -> ModelingExperiment | None:
        experiment = self.experiment_rows.get(experiment_id)
        return experiment if experiment and experiment.owner_id == owner_id else None

    async def experiments(self, owner_id: str) -> list[ModelingExperiment]:
        return [row for row in self.experiment_rows.values() if row.owner_id == owner_id]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def presign_put(self, key: str, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(url=f"https://storage.invalid/{key}", headers={"x-test": "1"})

    async def stat(self, key: str) -> SimpleNamespace:
        return SimpleNamespace(size=len(self.objects[key]))


def test_service_queues_owned_bundle_and_experiment() -> None:
    async def scenario() -> None:
        repository = FakeRepository()
        storage = FakeStorage()
        service = ModelingService(repository, storage)  # type: ignore[arg-type]
        payload = b"PK\x03\x04bundle"

        ticket = await service.create_upload(
            "user-1", "risk sample", "risk.zip", "application/zip", len(payload)
        )
        dataset = repository.dataset_rows[ticket.dataset_id]
        storage.objects[dataset.object_key] = payload

        queued = await service.complete_upload("user-1", dataset.id)
        assert queued.status == "queued"
        assert next(iter(repository.job_rows.values())).kind == "analyze_bundle"

        dataset.status = "ready"
        dataset.task_type = "loan_application"
        dataset.sample_unit = "loan_application"
        dataset.manifest = {
            "target": {"name": "default_12m", "positiveValue": 1},
            "features": [{"name": "debt_ratio"}, {"name": "company_age"}],
        }
        dataset.capabilities = {"tabular": True, "gnn": False, "relations": False}
        experiment = await service.run_experiment(
            "user-1",
            dataset.id,
            "baseline",
            "default_12m",
            "recommended",
            [],
            ["logistic_regression", "hist_gradient_boosting"],
            False,
            False,
            False,
            False,
            42,
        )
        assert experiment.status == "queued"
        assert experiment.model_type == "comparison_suite"
        assert len(repository.job_rows) == 2
        assert await service.get_experiment("user-1", experiment.id) is experiment

        with pytest.raises(ModelingError) as error:
            await service.get_dataset("user-2", dataset.id)
        assert error.value.code == "MODELING_DATASET_NOT_FOUND"

    asyncio.run(scenario())


def test_service_rejects_non_zip_upload() -> None:
    async def scenario() -> None:
        service = ModelingService(FakeRepository(), FakeStorage())  # type: ignore[arg-type]
        with pytest.raises(ModelingError) as error:
            await service.create_upload("user-1", "sample", "sample.csv", "text/csv", 50)
        assert error.value.code == "MODELING_FILE_INVALID"
        assert error.value.field == "filename"

    asyncio.run(scenario())
