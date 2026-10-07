import asyncio
import json
import os
import signal
import sys
from collections.abc import Awaitable, Callable


class ComputationFailed(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.retryable = exit_code < 0


async def run_cli(arguments: list[str], event: Callable[[str, dict], Awaitable[None]]):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "service.cli",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
        limit=1024 * 1024,
    )
    result = None
    tail: list[str] = []
    try:
        assert process.stdout is not None
        async for line in process.stdout:
            text = line.decode(errors="replace").strip()
            try:
                record = json.loads(text)
                kind, data = record["kind"], record["data"]
            except (ValueError, KeyError, TypeError):
                tail = (tail + [text])[-10:]
                await event("log", {"message": text[:4096]})
                continue
            if kind == "result":
                result = data
            else:
                await event(kind, data)
        status = await process.wait()
        if status != 0:
            raise ComputationFailed(
                "\n".join(tail)[-4096:] or f"Process exited with {status}", status
            )
        return result
    finally:
        if process.returncode is None:
            # Include descendants; cancelling an asyncio task alone does not stop computation.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            except ProcessLookupError:
                await process.wait()
