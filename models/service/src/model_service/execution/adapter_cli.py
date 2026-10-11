"""CLI protocol: request JSON in; typed events and sealed result/error files out."""

import argparse
import signal
import traceback
from pathlib import Path

from pydantic import TypeAdapter

from model_service.adapters.contracts import (
    AdapterError,
    AdapterEvent,
    ErrorDetail,
    ExecutionContext,
)
from model_service.adapters.registry import registry
from model_service.execution.invocation import Invocation, invoke
from model_service.files import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one registered model adapter operation")
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    invocation = Invocation.model_validate(read_json(args.request))
    invocation.directory.mkdir(parents=True, exist_ok=True)
    cancelled = False

    def cancel(_signal, _frame):
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, cancel)
    event_type: TypeAdapter[AdapterEvent] = TypeAdapter(AdapterEvent)
    # A separate channel means research stdout cannot masquerade as a result/event.
    with (invocation.directory / "events.jsonl").open("w") as stream:

        def emit(event: AdapterEvent) -> None:
            checked = event_type.validate_python(event)
            stream.write(checked.model_dump_json() + "\n")
            stream.flush()

        context = ExecutionContext(
            run_id=invocation.run_id,
            attempt_id=invocation.attempt_id,
            request_id=invocation.request_id,
            work_dir=invocation.directory / "work",
            output_dir=invocation.directory / "output",
            emit_event=emit,
            is_cancelled=lambda: cancelled,
            device=invocation.device,
            resources=invocation.resources,
        )
        try:
            adapter = registry.get(invocation.adapter_id, invocation.adapter_version)()
            invoke(adapter, invocation, context)
        except Exception as error:
            detail = (
                error.detail
                if isinstance(error, AdapterError)
                else ErrorDetail(
                    code="ADAPTER_EXECUTION_FAILED",
                    message="Adapter execution failed; see diagnostic log",
                )
            )
            write_json(invocation.directory / "error.json", detail.model_dump(mode="json"))
            traceback.print_exc()
            raise SystemExit(1) from error


if __name__ == "__main__":
    main()
