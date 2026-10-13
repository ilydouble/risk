"""Exercise the service supervisor with a real RiskGNN+ CLI in fresh processes."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from model_service.execution.artifacts import artifact_paths, fingerprint
from model_service.execution.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.invocation import Invocation, verify_receipt
from model_service.execution.process import run_model
from model_service.execution.runtime import runtime_spec


def test_plus_service_seals_real_model_and_reloads_predictions(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    python = os.getenv("RISK_MODEL_TEST_PYTHON", sys.executable)
    source = root / "datasets/comrisk_export_v5/smesd"
    assert source.is_dir(), "Real SMEsD data is required"
    archive = tmp_path / "source.zip"
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [
                str(root / "models"),
                str(root / "models/riskgnn+"),
            ]
        ),
    }
    packaged = subprocess.run(
        [
            python,
            "-c",
            "from pathlib import Path; from riskgnn.dataset_adapters.packaging import package; "
            "import sys; package(Path(sys.argv[1]),Path(sys.argv[2]),'smesd','service-plus', "
            "overrides={'target_count':30})",
            str(source),
            str(archive),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )
    assert packaged.returncode == 0, packaged.stderr
    original = asyncio.create_subprocess_exec

    async def compute(_python, *args, **kwargs):
        return await original(python, *args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", compute)
    seen = []

    async def event(kind, data):
        seen.append((kind, data))

    async def operation(name, role, path, format_name, parameters=None, configuration=None):
        spec = runtime_spec()
        invocation = Invocation(
            runtime_id=spec.runtime_id,
            runtime_version=spec.runtime_version,
            request=OperationRequest(
                operation=name,
                inputs={role: AssetInput(path=path, sha256=fingerprint(path), format=format_name)}
                if role
                else {},
                parameters=parameters or {},
                configuration=configuration or {},
            ),
            run_id="plus-service",
            attempt_id="1",
            request_id="test",
            directory=tmp_path / name.value,
        )
        receipt = await run_model(invocation, event)
        assert verify_receipt(invocation).binding == receipt.binding
        return invocation, receipt.result

    async def exercise():
        inspect_call, inspected = await operation(Operation.INSPECT, "dataset", archive, "zip")
        assert inspected.artifacts["enterprises"].format == "risk-enterprise-data-v1"
        assert artifact_paths(inspect_call.directory / "output", inspected)["enterprises"].is_file()
        _, configured = await operation(
            Operation.CONFIGURE,
            None,
            None,
            None,
            {
                "dataset_contract": inspected.data["datasetContract"],
                "requested_parameters": {"epochs": 1},
            },
        )
        assert configured.data["resolvedParameters"]["algorithm"] == "riskgnn-plus"
        call, trained = await operation(
            Operation.TRAIN,
            "dataset",
            archive,
            "zip",
            configured.data["resolvedParameters"],
            configured.data,
        )
        model = artifact_paths(call.directory / "output", trained)["model"]
        assert trained.artifacts["model"].format == "riskgnn-plus-model-v1"
        assert trained.data["profile"]["hyperedgeCount"] > 0
        before = fingerprint(model)
        _, tested = await operation(Operation.EVALUATE, "model", model, "riskgnn-plus-model-v1")
        assert tested.data["report"]["algorithm"] == "RiskGNN+"
        assert fingerprint(model) == before
        _, predicted = await operation(
            Operation.PREDICT,
            "model",
            model,
            "riskgnn-plus-model-v1",
            {"company_ids": trained.data["companies"][:2]},
        )
        assert len(predicted.data["items"]) == 2
        assert all(0 <= row["uncertainty"] <= 1 for row in predicted.data["items"])
        assert any(kind == "metric" for kind, _ in seen)

    asyncio.run(exercise())
