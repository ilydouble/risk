import asyncio
import csv
import io
from types import SimpleNamespace
from typing import Any

import pytest

from risk_api.modules.modeling.errors import ModelingError
from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment
from risk_api.modules.modeling.service import ModelingService


def make_csv() -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["debt_ratio", "lawsuit_count", "age", "defaulted"])
    for index in range(80):
        risky = index % 4 == 0
        writer.writerow(
            [0.8 if risky else 0.2, 3 if risky else 0, 2 if risky else 10, int(risky)]
        )
    return stream.getvalue().encode()


class FakeRepository:
    def __init__(self) -> None:
        self.dataset_rows: dict[str, ModelingDataset] = {}
        self.experiment_rows: dict[str, ModelingExperiment] = {}

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

    async def experiment(
        self, experiment_id: str, owner_id: str
    ) -> ModelingExperiment | None:
        experiment = self.experiment_rows.get(experiment_id)
        return experiment if experiment and experiment.owner_id == owner_id else None

    async def experiments(self, owner_id: str) -> list[ModelingExperiment]:
        return [row for row in self.experiment_rows.values() if row.owner_id == owner_id]


class FakeObject:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def __aenter__(self) -> "FakeObject":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self, size: int) -> bytes:
        return self.payload[:size]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def presign_put(self, key: str, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(url=f"https://storage.invalid/{key}", headers={"x-test": "1"})

    async def stat(self, key: str) -> SimpleNamespace:
        return SimpleNamespace(size=len(self.objects[key]))

    def open_object(self, key: str) -> FakeObject:
        return FakeObject(self.objects[key])


def test_service_completes_dataset_and_runs_owned_experiment() -> None:
    async def scenario() -> None:
        repository = FakeRepository()
        storage = FakeStorage()
        service = ModelingService(repository, storage)  # type: ignore[arg-type]
        payload = make_csv()

        ticket = await service.create_upload(
            "user-1", "risk sample", "risk.csv", "text/csv", len(payload)
        )
        dataset = repository.dataset_rows[ticket.dataset_id]
        storage.objects[dataset.object_key] = payload

        completed = await service.complete_upload("user-1", dataset.id)
        assert completed.status == "ready"
        assert completed.row_count == 80
        assert completed.analysis is not None

        experiment = await service.run_experiment(
            "user-1",
            dataset.id,
            "baseline",
            "defaulted",
            "1",
            ["debt_ratio", "lawsuit_count", "age"],
            42,
        )
        assert experiment.metrics["test"]["rows"] == 16
        assert await service.get_experiment("user-1", experiment.id) is experiment

        with pytest.raises(ModelingError) as error:
            await service.get_dataset("user-2", dataset.id)
        assert error.value.code == "MODELING_DATASET_NOT_FOUND"

    asyncio.run(scenario())


def test_service_rejects_non_csv_upload() -> None:
    async def scenario() -> None:
        service = ModelingService(FakeRepository(), FakeStorage())  # type: ignore[arg-type]
        with pytest.raises(ModelingError) as error:
            await service.create_upload("user-1", "sample", "sample.xlsx", "text/csv", 50)
        assert error.value.code == "MODELING_FILE_INVALID"
        assert error.value.field == "filename"

    asyncio.run(scenario())
