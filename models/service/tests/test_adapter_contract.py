"""Execution contracts contain no model inheritance or data loading API."""

import json
import subprocess
import sys

import pytest
from pydantic import TypeAdapter, ValidationError

from model_service.execution.artifacts import fingerprint
from model_service.execution.contracts import (
    Artifact,
    ArtifactSpec,
    AssetInput,
    EventKind,
    ExecutionError,
    ExecutionEvent,
    InputSpec,
    Operation,
    OperationRequest,
    OperationResult,
    OperationSpec,
    ProgressEvent,
    RuntimeSpec,
)
from model_service.execution.invocation import Invocation, finalize, validate_inputs, verify_receipt


def fixture_call(tmp_path):
    source = tmp_path / "numbers.txt"
    source.write_text("1 2 3")
    spec = RuntimeSpec(
        runtime_id="test",
        runtime_version="2",
        name="test",
        operations={
            Operation.EVALUATE: OperationSpec(
                inputs={"numbers": InputSpec(kind="file", formats=["text"])},
                parameters_schema={
                    "type": "object",
                    "properties": {"factor": {"type": "integer"}},
                    "additionalProperties": False,
                },
                artifacts={"answer": ArtifactSpec(kind="file", format="text")},
            )
        },
    )
    call = Invocation(
        runtime_id="test",
        runtime_version="2",
        run_id="run",
        attempt_id="1",
        request_id="request",
        directory=tmp_path / "operation",
        request=OperationRequest(
            operation=Operation.EVALUATE,
            inputs={"numbers": AssetInput(path=source, sha256=fingerprint(source), format="text")},
        ),
    )
    output = call.directory / "output"
    output.mkdir(parents=True)
    (output / "answer.txt").write_text("12")
    result = OperationResult(
        data={"sum": 12}, artifacts={"answer": Artifact(path="answer.txt", format="text")}
    )
    return spec, call, result


def test_result_sealing_and_corruption(tmp_path):
    spec, call, result = fixture_call(tmp_path)
    validate_inputs(call, spec)
    receipt = finalize(call, spec, result)
    assert verify_receipt(call) == receipt
    (call.directory / "output/answer.txt").write_text("changed")
    with pytest.raises(ExecutionError, match="checksum"):
        verify_receipt(call)


@pytest.mark.parametrize("parameters", [{"factor": "2"}, {"unknown": 1}])
def test_parameters_fail_before_execution(tmp_path, parameters):
    spec, call, _ = fixture_call(tmp_path)
    call = call.model_copy(
        update={"request": call.request.model_copy(update={"parameters": parameters})}
    )
    with pytest.raises(ExecutionError) as error:
        validate_inputs(call, spec)
    assert error.value.detail.code == "EXECUTION_PARAMETERS_INVALID"


def test_paths_and_input_immutability(tmp_path):
    spec, call, result = fixture_call(tmp_path)
    for path in (".", "../answer", "/answer", "a\\b"):
        with pytest.raises(ValidationError):
            Artifact(path=path, format="text")
    output = call.directory / "output/answer.txt"
    output.unlink()
    with pytest.raises(ExecutionError):
        finalize(call, spec, result)
    output.symlink_to(call.request.inputs["numbers"].path)
    with pytest.raises(ExecutionError):
        finalize(call, spec, result)
    call.request.inputs["numbers"].path.write_text("modified")
    with pytest.raises(ExecutionError, match="checksum"):
        validate_inputs(call, spec)


def test_event_enum_validation_and_lean_service_import():
    event_type = TypeAdapter(ExecutionEvent)
    assert event_type.validate_json('{"kind":"progress","current":2}').total is None
    assert event_type.validate_json('{"kind":"log","message":"test"}').kind is EventKind.LOG
    for value in ({"kind": "completed"}, {"kind": "metric", "name": "loss", "value": float("nan")}):
        with pytest.raises(ValidationError):
            event_type.validate_python(value)
    with pytest.raises(ValidationError):
        ProgressEvent(current=3, total=2)
    script = """import sys,json
from model_service.app import create_app
from model_service.execution.runtime import runtime_spec
runtime_spec()
blocked={'torch','numpy','riskgnn'}
print(json.dumps(sorted(n for n in sys.modules if n.split('.')[0] in blocked)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == []
