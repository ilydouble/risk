import asyncio

import numpy as np
import pytest

from model_service.adapters.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.artifacts import fingerprint, inventory, pack
from model_service.execution.invocation import Invocation
from model_service.execution.process import ComputationFailed, run_adapter
from model_service.runtime.predictor import Predictor


def test_registered_riskgnn_cli_train_independent_test_predict(export_zip, tmp_path):
    events = []

    async def event(kind, data):
        events.append((kind, data))

    async def operation(name, role, path, format, parameters=None):
        call = Invocation(
            adapter_id="riskgnn-node-edge",
            adapter_version="1.0.0",
            request=OperationRequest(
                operation=name,
                inputs={role: AssetInput(path=path, sha256=fingerprint(path), format=format)},
                parameters=parameters or {},
            ),
            run_id="flow",
            attempt_id="1",
            request_id="request",
            directory=tmp_path / (name.value + str(len(events))),
        )
        receipt = await run_adapter(call, event)
        return call, receipt.result

    async def exercise():
        _, inspected = await operation(Operation.INSPECT, "dataset", export_zip, "zip")
        assert inspected.data["compatibility"] == "compatible"
        assert inspected.data["counts"]["company_attr"] == 90
        call, trained = await operation(
            Operation.TRAIN, "dataset", export_zip, "zip", {"epochs": 1}
        )
        model = call.directory / "output" / trained.artifacts["model"].path
        before = inventory(model)
        _, tested = await operation(Operation.EVALUATE, "model", model, "riskgnn-model-v1")
        assert tested.data["report"]["independentReload"] is True
        assert tested.data["report"]["modelSha256"] == fingerprint(model)
        assert before == inventory(model), "Independent testing must not mutate the trained model"
        ids = trained.data["companies"][:3]
        _, predicted = await operation(
            Operation.PREDICT, "model", model, "riskgnn-model-v1", {"company_ids": ids[::-1]}
        )
        reference = Predictor(model).predict(ids[::-1])
        assert [r["companyId"] for r in predicted.data["items"]] == ids[::-1]
        assert np.allclose(
            [r["probability"] for r in reference],
            [r["probability"] for r in predicted.data["items"]],
            atol=1e-7,
        )
        with pytest.raises(ComputationFailed) as error:
            await operation(
                Operation.PREDICT, "model", model, "riskgnn-model-v1", {"company_ids": ["missing"]}
            )
        assert error.value.detail.code == "RISKGNN_COMPANY_NOT_FOUND"
        assert not error.value.detail.retryable
        pack(model, tmp_path / "download.zip")
        assert (
            len([1 for kind, data in events if kind == "metric" and data["group"] == "train"]) == 1
        )

    asyncio.run(exercise())
