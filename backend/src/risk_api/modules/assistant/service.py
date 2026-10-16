import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from time import monotonic

from anyio import CancelScope

from risk_api.errors import AppError
from risk_api.modules.assistant.protocol.events import TurnEvent
from risk_api.modules.assistant.protocol.items import Item
from risk_api.modules.assistant.protocol.turns import Turn, TurnError, TurnStatus
from risk_api.modules.assistant.repository import AssistantRepository
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, repository: AssistantRepository, runtime: StrandsRuntime):
        self.repository = repository
        self.runtime = runtime
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.start_lock = asyncio.Lock()
        self.closed = False

    async def start(
        self,
        owner: str,
        conversation: str,
        key: str,
        message: str,
        settings: ModelSettings,
        request_id: str,
    ) -> Turn:
        async with self.start_lock:
            turn, created = await self.repository.start(
                owner,
                conversation,
                key,
                message,
                settings.public(),
                request_id,
                accept_new=not self.closed and len(self.tasks) < 8,
            )
            if created:
                task = asyncio.create_task(self.execute(owner, turn, message, settings))
                self.tasks[turn.id] = task
                task.add_done_callback(lambda _: self.tasks.pop(turn.id, None))
            return turn

    async def execute(self, owner: str, turn: Turn, message: str, settings: ModelSettings) -> None:
        async def supervise() -> None:
            while True:
                await asyncio.sleep(2)
                # Heartbeat also observes cancellation from another API instance.
                try:
                    alive = await self.repository.heartbeat(turn.id)
                except Exception:
                    alive = False
                    logger.error("assistant.heartbeat_failed", extra={"turn_id": turn.id})
                if not alive:
                    if runner is not None:
                        runner.cancel()
                    return

        monitor = asyncio.create_task(supervise())
        runner = asyncio.current_task()
        assert runner is not None
        status, error = TurnStatus.COMPLETED, None
        logger.info(
            "assistant.turn_started", extra={"turn_id": turn.id, "request_id": turn.requestId}
        )
        try:
            async with asyncio.timeout(180):
                history = await self.repository.history(owner, turn.conversationId)
                # Drain with a bounded queue and coalesce snapshots, preserving item creation order.
                queue: asyncio.Queue[list[Item] | Exception | None] = asyncio.Queue(maxsize=32)

                async def produce() -> None:
                    try:
                        async with aclosing(
                            self.runtime.stream(message, history, settings, turn.requestId, owner)
                        ) as stream:
                            async for items in stream:
                                await queue.put(items)
                    except Exception as failure:
                        await queue.put(failure)
                    else:
                        await queue.put(None)

                producer = asyncio.create_task(produce())
                try:
                    pending: dict[str, Item] = {}
                    flushed = monotonic()
                    while True:
                        try:
                            batch = await asyncio.wait_for(queue.get(), timeout=0.12)
                        except TimeoutError:
                            batch = []
                        if isinstance(batch, Exception):
                            raise batch
                        for item in batch or []:
                            pending[item.id] = item
                        if pending and (monotonic() - flushed >= 0.12 or batch is None):
                            if not await self.repository.update_items(
                                turn.id, list(pending.values())
                            ):
                                raise asyncio.CancelledError
                            pending.clear()
                            flushed = monotonic()
                        if batch is None:
                            break
                finally:
                    producer.cancel()
                    await asyncio.gather(producer, return_exceptions=True)
        except asyncio.CancelledError:
            status = TurnStatus.INTERRUPTED
            error = TurnError(code="ASSISTANT_INTERRUPTED", message="Execution interrupted")
        except AppError as failure:
            status = TurnStatus.FAILED
            error = (TurnError(code=failure.code, message=failure.message)
                     if failure.code == "ASSISTANT_EXECUTION_LIMIT" else
                     TurnError(code="ASSISTANT_EXECUTION_FAILED", message="执行未完成，请稍后重试"))
            logger.warning("assistant.turn_failed", extra={
                "turn_id": turn.id, "request_id": turn.requestId, "internal_code": failure.code,
            })
        except Exception as failure:
            status = TurnStatus.FAILED
            error = TurnError(
                code="ASSISTANT_EXECUTION_FAILED",
                message="Model execution failed; check model settings or retry",
            )
            # Provider exception strings may contain secrets or upstream response bodies.
            logger.warning(
                "assistant.turn_failed",
                extra={
                    "turn_id": turn.id,
                    "request_id": turn.requestId,
                    "cause_type": type(failure).__name__,
                },
            )
        finally:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            try:
                await self.repository.finish(turn.id, status, error)
                status = (await self.repository.turn(owner, turn.id)).status
            except Exception:
                logger.error("assistant.finalize_failed", extra={"turn_id": turn.id})
            logger.info("assistant.turn_finished", extra={"turn_id": turn.id, "status": status})

    async def cancel(self, owner: str, turn_id: str) -> Turn:
        await self.repository.turn(owner, turn_id)
        await self.repository.finish(turn_id, TurnStatus.CANCELLED)
        task = self.tasks.get(turn_id)
        if task:
            task.cancel()
        return await self.repository.turn(owner, turn_id)

    async def events(self, owner: str, turn_id: str, after: int) -> AsyncIterator[str]:
        yield ": connected\n\n"
        heartbeat = monotonic()
        while True:
            # A browser disconnect cancels Starlette's AnyIO scope repeatedly. Finish the
            # short DB read/connection return before yielding to cancellation at sleep/yield.
            with CancelScope(shield=True):
                async with asyncio.timeout(5):
                    events, done = await self.repository.events(owner, turn_id, after)
            for event in events:
                yield self.encode(event)
                after = event.sequence
            if done:
                return
            if monotonic() - heartbeat >= 10:
                yield ": heartbeat\n\n"
                heartbeat = monotonic()
            await asyncio.sleep(0.25)

    @staticmethod
    def encode(event: TurnEvent) -> str:
        return f"id: {event.sequence}\nevent: turn_event\ndata: {event.model_dump_json()}\n\n"

    async def maintain(self) -> None:
        while True:
            try:
                await self.repository.recover_expired()
            except Exception:
                logger.error("assistant.recovery_failed")
            await asyncio.sleep(10)

    async def close(self) -> None:
        self.closed = True
        active = list(self.tasks.items())
        tasks = [task for _, task in active]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for turn_id, _ in active:
            await self.repository.finish(
                turn_id,
                TurnStatus.INTERRUPTED,
                TurnError(code="ASSISTANT_INTERRUPTED", message="Service stopped"),
            )
