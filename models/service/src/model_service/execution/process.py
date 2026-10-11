import asyncio
import os
import signal
import sys
from collections.abc import Awaitable, Callable

from pydantic import TypeAdapter

from model_service.execution.contracts import (
    ErrorDetail,
    ExecutionError,
    ExecutionEvent,
    OperationResult,
    parameters_for,
)
from model_service.execution.invocation import Invocation, Receipt, finalize, validate_inputs
from model_service.execution.runtime import model_root, runtime_spec
from model_service.files import read_json, write_json
from model_service.shared.dataset_contract import read_dataset_contract


class ComputationFailed(ExecutionError):
    pass


async def run_model(
    invocation: Invocation, event: Callable[[str, dict], Awaitable[None]]
) -> Receipt:
    spec = runtime_spec()
    await asyncio.to_thread(validate_inputs, invocation, spec)
    if "dataset" in invocation.request.inputs:
        await asyncio.to_thread(read_dataset_contract, invocation.request.inputs["dataset"].path)
    directory = invocation.directory
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("error.json", "result.json", "operation-result.json", "events.jsonl"):
        (directory / name).unlink(missing_ok=True)
    request = directory / "request.json"
    payload = invocation.model_dump(mode="json")
    payload["request"]["parameters"] = parameters_for(
        spec, invocation.request.operation, invocation.request.parameters
    )
    write_json(request, payload)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "riskgnn.workbench_cli",
        "--request",
        str(request),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
        cwd=model_root(),
        limit=1024 * 1024,
    )
    finished = asyncio.Event()
    event_type: TypeAdapter[ExecutionEvent] = TypeAdapter(ExecutionEvent)

    async def logs():
        assert process.stdout is not None
        async for line in process.stdout:
            await event(
                "log", {"level": "info", "message": line.decode(errors="replace").strip()[:4096]}
            )
        await process.wait()
        finished.set()

    async def events():
        offset = 0
        pending = ""
        while True:
            path = directory / "events.jsonl"
            if path.exists():
                with path.open() as stream:
                    stream.seek(offset)
                    pending += stream.read()
                    offset = stream.tell()
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    record = event_type.validate_json(line)
                    await event(record.kind.value, record.model_dump(mode="json", exclude={"kind"}))
            if finished.is_set():
                if pending:
                    raise ComputationFailed("EXECUTION_PROTOCOL_INVALID", "Incomplete event record")
                return
            await asyncio.sleep(0.1)

    consumers = [asyncio.create_task(logs()), asyncio.create_task(events())]
    try:
        await asyncio.gather(*consumers)
        if process.returncode != 0:
            error_path = directory / "error.json"
            if error_path.exists():
                detail = ErrorDetail.model_validate(read_json(error_path))
                raise ComputationFailed(
                    detail.code, detail.message, path=detail.path, retryable=detail.retryable
                )
            # A crash/OOM is not proof of a transient error. Lease expiry already
            # recovers killed workers; adapters explicitly classify retriable failures.
            raise ComputationFailed(
                "EXECUTION_PROCESS_FAILED", f"Process exited with {process.returncode}"
            )
        if not (directory / "operation-result.json").is_file():
            raise ComputationFailed(
                "EXECUTION_RESULT_MISSING", "Process exited without a sealed result"
            )
        result = OperationResult.model_validate(read_json(directory / "operation-result.json"))
        return await asyncio.to_thread(finalize, invocation, spec, result)
    finally:
        for consumer in consumers:
            consumer.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        # Also terminate descendants after the parent has exited: a lingering
        # child can otherwise keep stdout open and survive task cancellation.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
