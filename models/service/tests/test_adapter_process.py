import asyncio
import sys

import pytest

from model_service.adapters.contracts import Operation, OperationRequest
from model_service.execution.invocation import Invocation
from model_service.execution.process import ComputationFailed, run_adapter


def call(tmp_path):
    return Invocation(
        adapter_id="test",
        adapter_version="1",
        request=OperationRequest(operation=Operation.EVALUATE),
        run_id="test",
        attempt_id="1",
        request_id="test",
        directory=tmp_path,
    )


def test_stdout_is_log_and_zero_exit_requires_sealed_result(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec

    async def substitute(*_args, **kwargs):
        return await original(
            sys.executable, "-c", 'print(\'{"kind":"result","data":{}}\')', **kwargs
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", substitute)
    seen = []

    async def event(kind, data):
        seen.append((kind, data))

    with pytest.raises(ComputationFailed) as error:
        asyncio.run(run_adapter(call(tmp_path), event))
    assert error.value.detail.code == "ADAPTER_RESULT_MISSING"
    assert all(kind == "log" for kind, _ in seen)


def test_supervisor_cancellation_stops_compute_process(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    processes = []

    async def substitute(*_args, **kwargs):
        process = await original(
            sys.executable, "-u", "-c", 'import time; print("ready"); time.sleep(120)', **kwargs
        )
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", substitute)

    async def exercise():
        ready = asyncio.Event()

        async def event(_kind, _data):
            ready.set()

        task = asyncio.create_task(run_adapter(call(tmp_path), event))
        await asyncio.wait_for(ready.wait(), 10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert processes[0].returncode is not None

    asyncio.run(exercise())
