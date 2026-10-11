import asyncio
import os
import signal
import sys
from collections.abc import Awaitable, Callable

from pydantic import TypeAdapter

from model_service.adapters.contracts import AdapterError, AdapterEvent, ErrorDetail
from model_service.execution.invocation import Invocation, Receipt, verify_receipt
from model_service.files import read_json, write_json


class ComputationFailed(AdapterError):
    pass


async def run_adapter(
    invocation: Invocation, event: Callable[[str, dict], Awaitable[None]]
) -> Receipt:
    directory = invocation.directory
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("error.json", "result.json", "events.jsonl"):
        (directory / name).unlink(missing_ok=True)
    request = directory / "request.json"
    write_json(request, invocation.model_dump(mode="json"))
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "model_service.execution.adapter_cli",
        "--request",
        str(request),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
        limit=1024 * 1024,
    )
    finished = asyncio.Event()
    event_type: TypeAdapter[AdapterEvent] = TypeAdapter(AdapterEvent)

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
                    raise ComputationFailed("ADAPTER_PROTOCOL_INVALID", "Incomplete event record")
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
                "ADAPTER_PROCESS_FAILED", f"Process exited with {process.returncode}"
            )
        if not (directory / "result.json").is_file():
            raise ComputationFailed(
                "ADAPTER_RESULT_MISSING", "Process exited without a sealed result"
            )
        return await asyncio.to_thread(verify_receipt, invocation)
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
