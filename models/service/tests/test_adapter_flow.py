import asyncio

import numpy as np
import pytest

from model_service.execution.artifacts import fingerprint, inventory, pack
from model_service.execution.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.invocation import Invocation
from model_service.execution.process import ComputationFailed, run_model
from riskgnn.dataset_adapters.packaging import package
from riskgnn.workbench.artifacts import read_json
from riskgnn.workbench.predictor import Predictor


@pytest.fixture(params=["acra", "smesd", "uk-dataset-v1"])
def real_training_zip(request, export_zip, datasets, tmp_path):
    if request.param == "acra":
        return export_zip
    folder = "comrisk_export_v5/smesd" if request.param == "smesd" else "uk_dataset_v1"
    path = tmp_path / "real-json.zip"
    package(
        datasets / folder,
        path,
        ("smesd" if request.param == "smesd" else "uk-companies-legacy"),
        "real-local",
        overrides={"target_count": 60},
    )
    return path


def test_registered_riskgnn_cli_train_independent_test_predict(real_training_zip, tmp_path):
    export_zip = real_training_zip
    events = []

    async def event(kind, data):
        events.append((kind, data))

    async def operation(
        name, role=None, path=None, format=None, parameters=None, configuration=None
    ):
        call = Invocation(
            runtime_id="riskgnn",
            runtime_version="3",
            request=OperationRequest(
                operation=name,
                inputs={role: AssetInput(path=path, sha256=fingerprint(path), format=format)}
                if role
                else {},
                parameters=parameters or {},
                configuration=configuration or {},
            ),
            run_id="flow",
            attempt_id="1",
            request_id="request",
            directory=tmp_path / (name.value + str(len(events))),
        )
        receipt = await run_model(call, event)
        return call, receipt.result

    async def exercise():
        _, inspected = await operation(Operation.INSPECT, "dataset", export_zip, "zip")
        assert inspected.data["compatibility"] == "compatible"
        assert inspected.data["counts"]["company_attr"] > 48
        _, configured = await operation(
            Operation.CONFIGURE,
            parameters={
                "dataset_contract": inspected.data["datasetContract"],
                "requested_parameters": {"epochs": 1, "dataset": {"target_count": 30}},
            },
        )
        call, trained = await operation(
            Operation.TRAIN,
            "dataset",
            export_zip,
            "zip",
            configured.data["resolvedParameters"],
            configured.data,
        )
        model = call.directory / "output" / trained.artifacts["model"].path
        metadata = read_json(model / "metadata.json")
        assert metadata["configuration"] == configured.data
        assert trained.effective_config == configured.data["resolvedParameters"]
        assert metadata["actualCounts"]["targets"] == 30
        assert sum(metadata["actualCounts"][key] for key in ("train", "validation", "test")) == 30
        before = inventory(model)
        _, tested = await operation(Operation.EVALUATE, "model", model, "riskgnn-plus-model-v1")
        assert tested.data["report"]["independentReload"] is True
        assert tested.data["report"]["modelSha256"] == fingerprint(model)
        assert before == inventory(model), "Independent testing must not mutate the trained model"
        ids = trained.data["companies"][:3]
        _, predicted = await operation(
            Operation.PREDICT, "model", model, "riskgnn-plus-model-v1", {"company_ids": ids[::-1]}
        )
        reference = Predictor(model).predict(ids[::-1])
        assert [r["companyId"] for r in predicted.data["items"]] == ids[::-1]
        assert np.allclose(
            [r["probability"] for r in reference],
            [r["probability"] for r in predicted.data["items"]],
            atol=1e-7,
        )
        _, explained = await operation(
            Operation.PREDICT, "model", model, "riskgnn-plus-model-v1",
            {"company_ids": [ids[0]], "explain": True},
        )
        assert explained.data["items"][0]["explanation"]["features"]
        assert inventory(model) == before
        with pytest.raises(ComputationFailed) as error:
            await operation(
                Operation.PREDICT,
                "model",
                model,
                "riskgnn-plus-model-v1",
                {"company_ids": ["missing"]},
            )
        assert error.value.detail.code == "RISKGNN_COMPANY_NOT_FOUND"
        assert not error.value.detail.retryable
        pack(model, tmp_path / "download.zip")
        assert (
            len([1 for kind, data in events if kind == "metric" and data["group"] == "train"]) == 1
        )

    asyncio.run(exercise())
