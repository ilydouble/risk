"""Contracts are independent of any dataset layout, graph library or HTTP API."""

import json
import subprocess
import sys

import pytest
from pydantic import TypeAdapter, ValidationError

from model_service.adapters.contracts import (
    AdapterCancelled,
    AdapterError,
    AdapterEvent,
    AdapterSpec,
    Artifact,
    ArtifactSpec,
    AssetInput,
    EventKind,
    ExecutionContext,
    InputSpec,
    MetricEvent,
    ModelAdapter,
    Operation,
    OperationRequest,
    OperationResult,
    OperationSpec,
    ProgressEvent,
)
from model_service.execution.artifacts import fingerprint
from model_service.execution.invocation import Invocation, invoke, verify_receipt


class SumAdapter(ModelAdapter):
    """Test extension using text input; it has no train/graph/split conventions."""

    @classmethod
    def describe(cls):
        return AdapterSpec(
            adapter_id="sum",
            adapter_version="1",
            name="Sum",
            operations={
                Operation.EVALUATE: OperationSpec(
                    inputs={"numbers": InputSpec(kind="file", formats=["text"])},
                    parameters_schema={
                        "type": "object",
                        "properties": {"factor": {"type": "integer"}},
                        "required": ["factor"],
                        "additionalProperties": False,
                    },
                    default_parameters={"factor": 2},
                    result_schema={
                        "type": "object",
                        "properties": {"sum": {"type": "integer"}},
                        "required": ["sum"],
                    },
                    artifacts={"answer": ArtifactSpec(kind="file", format="text")},
                )
            },
        )

    def execute(self, request, context):
        value = sum(map(int, request.inputs["numbers"].path.read_text().split()))
        value *= request.parameters["factor"]
        (context.output_dir / "answer.txt").write_text(str(value))
        context.emit(MetricEvent(name="sum", value=value))
        return OperationResult(
            data={"sum": value},
            artifacts={"answer": Artifact(path="answer.txt", format="text")},
            effective_config=request.parameters,
        )


def fixture_call(tmp_path):
    source = tmp_path / "numbers.txt"
    source.write_text("1 2 3")
    call = Invocation(
        adapter_id="sum",
        adapter_version="1",
        run_id="run",
        attempt_id="1",
        request_id="request",
        directory=tmp_path / "attempt1",
        request=OperationRequest(
            operation=Operation.EVALUATE,
            inputs={"numbers": AssetInput(path=source, sha256=fingerprint(source), format="text")},
        ),
    )
    events = []
    context = ExecutionContext(
        run_id="run",
        attempt_id="1",
        request_id="request",
        work_dir=call.directory / "work",
        output_dir=call.directory / "output",
        emit_event=events.append,
    )
    return call, context, events


def test_capability_contract_and_model_free_execution(tmp_path):
    with pytest.raises(TypeError):
        ModelAdapter()
    call, context, events = fixture_call(tmp_path)
    result = invoke(SumAdapter(), call, context).result
    assert result.data == {"sum": 12} and result.effective_config == {"factor": 2}
    assert events[0].kind is EventKind.METRIC
    assert verify_receipt(call).result == result
    assert "evaluate" in SumAdapter.describe().model_dump(mode="json")["operations"]

    (call.directory / "output/answer.txt").write_text("tampered")
    with pytest.raises(AdapterError, match="checksum"):
        verify_receipt(call)


@pytest.mark.parametrize("parameters", [{"factor": "2"}, {"unknown": 1}])
def test_parameters_fail_before_adapter_executes(tmp_path, parameters):
    call, context, _ = fixture_call(tmp_path)
    call = call.model_copy(
        update={"request": call.request.model_copy(update={"parameters": parameters})}
    )
    with pytest.raises(AdapterError) as error:
        invoke(SumAdapter(), call, context)
    assert error.value.detail.code == "ADAPTER_PARAMETERS_INVALID"
    assert not context.output_dir.exists()


def test_cancel_missing_wrong_or_escaping_artifacts(tmp_path):
    call, context, _ = fixture_call(tmp_path)
    from dataclasses import replace

    with pytest.raises(AdapterCancelled):
        invoke(SumAdapter(), call, replace(context, is_cancelled=lambda: True))
    for path in ("../answer", "/answer", "a\\b"):
        with pytest.raises(ValidationError):
            Artifact(path=path, format="text")

    class BadAdapter(SumAdapter):
        def execute(self, request, context):
            return OperationResult(
                data={"sum": 1}, artifacts={"answer": Artifact(path="missing.txt", format="text")}
            )

    with pytest.raises(AdapterError) as error:
        invoke(BadAdapter(), call, context)
    assert error.value.detail.code == "ADAPTER_ARTIFACT_INVALID"

    class LinkedAdapter(SumAdapter):
        def execute(self, request, context):
            (context.output_dir / "answer.txt").symlink_to(call.request.inputs["numbers"].path)
            return OperationResult(
                data={"sum": 1}, artifacts={"answer": Artifact(path="answer.txt", format="text")}
            )

    with pytest.raises(AdapterError):
        invoke(LinkedAdapter(), call, context)


def test_event_enum_validation_and_lean_import():
    event_type = TypeAdapter(AdapterEvent)
    assert event_type.validate_json('{"kind":"progress","current":2}').total is None
    for value in ({"kind": "completed"}, {"kind": "metric", "name": "loss", "value": float("nan")}):
        with pytest.raises(ValidationError):
            event_type.validate_python(value)
    with pytest.raises(ValidationError):
        ProgressEvent(current=3, total=2)
    script = """import sys, json
from model_service.adapters.contracts import ModelAdapter, AdapterSpec
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in
    {'torch', 'numpy', 'fastapi', 'sqlalchemy', 'riskgnn'})))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
