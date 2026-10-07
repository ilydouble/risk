import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.workbench_model import Dispatch

logger = logging.getLogger(__name__)


async def deliver_one(sessions: async_sessionmaker[AsyncSession], client: ModelClient) -> bool:
    # This short lock protects delivery only. Model execution has its own durable lease.
    async with sessions.begin() as session:
        entry = await session.scalar(
            select(Dispatch)
            .where(Dispatch.delivered.is_(False), Dispatch.available_at <= datetime.now(UTC))
            .order_by(Dispatch.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if entry is None:
            return False
        try:
            await client.call("jobs/" + entry.operation, entry.payload, entry.request_id)
        except Exception as error:
            entry.attempts += 1
            entry.error = type(error).__name__
            entry.available_at = datetime.now(UTC) + timedelta(
                seconds=min(60, 2 ** min(entry.attempts, 5))
            )
            logger.warning(
                "model.dispatch_retry",
                extra={
                    "operation_id": entry.id,
                    "request_id": entry.request_id,
                    "attempt": entry.attempts,
                },
            )
        else:
            entry.delivered, entry.error = True, None
        return True


async def dispatch_loop(sessions: async_sessionmaker[AsyncSession], client: ModelClient) -> None:
    while True:
        try:
            delivered = await deliver_one(sessions, client)
        except asyncio.CancelledError:
            raise
        except Exception:
            delivered = False
            logger.exception("model.dispatch_failed")
        await asyncio.sleep(0.1 if delivered else 2)
