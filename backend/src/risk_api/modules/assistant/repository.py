import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from risk_api.errors import AppError
from risk_api.modules.assistant.model import (
    ConversationRecord,
    EventRecord,
    ItemRecord,
    TurnRecord,
)
from risk_api.modules.assistant.protocol.events import EventType, ItemDelta, TurnEvent
from risk_api.modules.assistant.protocol.items import Item, ItemStatus, TextItem
from risk_api.modules.assistant.protocol.turns import Conversation, Turn, TurnError, TurnStatus

item_parser: TypeAdapter[Item] = TypeAdapter(Item)


def now() -> datetime:
    return datetime.now(UTC)


class AssistantRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def owned(
        self, session: AsyncSession, owner: str, conversation: str
    ) -> ConversationRecord:
        row = await session.scalar(
            select(ConversationRecord).where(
                ConversationRecord.id == conversation, ConversationRecord.owner_id == owner
            )
        )
        if row is None:
            raise AppError(404, "ASSISTANT_NOT_FOUND", "Conversation or turn not found")
        return row

    async def create_conversation(self, owner: str) -> Conversation:
        async with self.sessions.begin() as session:
            row = ConversationRecord(id=str(uuid4()), owner_id=owner, title="", updated_at=now())
            session.add(row)
            return Conversation(id=row.id, title=row.title, updatedAt=row.updated_at)

    async def conversations(self, owner: str) -> list[Conversation]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(ConversationRecord)
                .where(ConversationRecord.owner_id == owner)
                .order_by(ConversationRecord.updated_at.desc())
                .limit(100)
            )
            return [Conversation(id=r.id, title=r.title, updatedAt=r.updated_at) for r in rows]

    async def view(self, session: AsyncSession, row: TurnRecord) -> Turn:
        items = await session.scalars(
            select(ItemRecord).where(ItemRecord.turn_id == row.id).order_by(ItemRecord.position)
        )
        return Turn(
            id=row.id,
            conversationId=row.conversation_id,
            status=TurnStatus(row.status),
            model=row.configuration["model"],
            requestId=row.request_id,
            sequence=row.sequence,
            createdAt=row.created_at,
            items=[item_parser.validate_python(i.payload) for i in items],
            error=TurnError.model_validate(row.error) if row.error else None,
        )

    async def history(self, owner: str, conversation: str) -> list[Turn]:
        async with self.sessions() as session:
            await self.owned(session, owner, conversation)
            rows = list(
                await session.scalars(
                    select(TurnRecord)
                    .where(TurnRecord.conversation_id == conversation)
                    .order_by(TurnRecord.created_at.desc(), TurnRecord.id.desc())
                    .limit(100)
                )
            )
            return [await self.view(session, r) for r in reversed(rows)]

    async def append(self, session: AsyncSession, row: TurnRecord, event: TurnEvent) -> None:
        row.sequence += 1
        event.sequence = row.sequence
        if event.item is not None:
            item = await session.get(ItemRecord, event.item.id)
            payload = event.item.model_dump(mode="json")
            if item is None:
                session.add(
                    ItemRecord(
                        id=event.item.id, turn_id=row.id, position=row.sequence, payload=payload
                    )
                )
            else:
                # Persist the latest snapshot, but send append-only text to avoid quadratic
                # event storage for long answers. Completion events remain full snapshots.
                field: Literal["text", "argumentsText"] = (
                    "argumentsText" if event.item.kind == "tool_call" else "text"
                )
                previous = item.payload.get(field, "")
                current = payload.get(field, "")
                if (
                    payload.get("status") == "running"
                    and current.startswith(previous)
                    and {k: v for k, v in payload.items() if k != field}
                    == {k: v for k, v in item.payload.items() if k != field}
                ):
                    event.type = EventType.ITEM_DELTA
                    event.delta = ItemDelta(
                        itemId=event.item.id, field=field, text=current[len(previous) :]
                    )
                    event.item = None
                item.payload = payload
        session.add(
            EventRecord(
                turn_id=row.id, sequence=row.sequence, payload=event.model_dump(mode="json")
            )
        )

    async def start(
        self,
        owner: str,
        conversation: str,
        key: str,
        message: str,
        configuration: dict[str, Any],
        request_id: str,
    ) -> tuple[Turn, bool]:
        digest = hashlib.sha256(
            json.dumps([message, configuration], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        async with self.sessions.begin() as session:
            await self.owned(session, owner, conversation)
            # Serialize competing browser tabs/instances on the parent row, including idempotency.
            parent = (
                await session.scalars(
                    select(ConversationRecord)
                    .where(ConversationRecord.id == conversation)
                    .with_for_update()
                )
            ).one()
            existing = await session.scalar(
                select(TurnRecord).where(
                    TurnRecord.conversation_id == conversation, TurnRecord.request_key == key
                )
            )
            if existing:
                if existing.input_digest != digest:
                    raise AppError(409, "ASSISTANT_KEY_CONFLICT", "Request key already used")
                return await self.view(session, existing), False
            active = await session.scalar(
                select(TurnRecord.id).where(
                    TurnRecord.conversation_id == conversation, TurnRecord.status == "running"
                )
            )
            if active:
                raise AppError(409, "ASSISTANT_BUSY", "Conversation is already running")
            row = TurnRecord(
                id=str(uuid4()),
                conversation_id=conversation,
                request_key=key,
                input_digest=digest,
                status="running",
                configuration=configuration,
                request_id=request_id,
                sequence=0,
                lease_until=now() + timedelta(seconds=60),
                created_at=now(),
            )
            session.add(row)
            await session.flush()
            parent.title = parent.title or message[:160]
            parent.updated_at = now()
            await self.append(
                session,
                row,
                TurnEvent(
                    turnId=row.id,
                    sequence=0,
                    type=EventType.TURN_STARTED,
                    status=TurnStatus.RUNNING,
                ),
            )
            await self.append(
                session,
                row,
                TurnEvent(
                    turnId=row.id,
                    sequence=0,
                    type=EventType.ITEM_UPDATED,
                    item=TextItem(kind="user_message", text=message, status=ItemStatus.COMPLETED),
                ),
            )
            await session.flush()
            return await self.view(session, row), True

    async def turn(self, owner: str, turn_id: str) -> Turn:
        async with self.sessions() as session:
            row = await session.get(TurnRecord, turn_id)
            if row is None:
                raise AppError(404, "ASSISTANT_NOT_FOUND", "Turn not found")
            await self.owned(session, owner, row.conversation_id)
            return await self.view(session, row)

    async def events(self, owner: str, turn_id: str, after: int) -> tuple[list[TurnEvent], bool]:
        async with self.sessions() as session:
            row = await session.get(TurnRecord, turn_id)
            if row is None:
                raise AppError(404, "ASSISTANT_NOT_FOUND", "Turn not found")
            await self.owned(session, owner, row.conversation_id)
            payloads: Any = await session.execute(
                select(EventRecord.payload)
                .where(EventRecord.turn_id == turn_id, EventRecord.sequence > after)
                .order_by(EventRecord.sequence)
                .limit(200)
            )
            events = [TurnEvent.model_validate(p) for p in payloads.scalars()]
            last = events[-1].sequence if events else after
            return events, row.status != "running" and last >= row.sequence

    async def update_items(self, turn_id: str, items: list[Item]) -> bool:
        async with self.sessions.begin() as session:
            row = await session.get(TurnRecord, turn_id, with_for_update=True)
            if row is None or row.status != "running" or row.lease_until < now():
                return False
            for item in items:
                await self.append(
                    session,
                    row,
                    TurnEvent(turnId=row.id, sequence=0, type=EventType.ITEM_UPDATED, item=item),
                )
            return True

    async def heartbeat(self, turn_id: str) -> bool:
        async with self.sessions.begin() as session:
            row = await session.get(TurnRecord, turn_id, with_for_update=True)
            if row is None or row.status != "running" or row.lease_until < now():
                return False
            row.lease_until = now() + timedelta(seconds=60)
            return True

    async def finish(
        self, turn_id: str, status: TurnStatus, error: TurnError | None = None
    ) -> None:
        async with self.sessions.begin() as session:
            row = await session.get(TurnRecord, turn_id, with_for_update=True)
            if row is None or row.status != "running":
                return
            # Expired executors may never publish a successful result.
            if row.lease_until < now():
                status = TurnStatus.INTERRUPTED
                error = TurnError(code="ASSISTANT_INTERRUPTED", message="Execution interrupted")
            items = list(
                await session.scalars(select(ItemRecord).where(ItemRecord.turn_id == row.id))
            )
            for saved in items:
                item = item_parser.validate_python(saved.payload)
                if item.status == ItemStatus.RUNNING:
                    item.status = (
                        ItemStatus.COMPLETED
                        if status == TurnStatus.COMPLETED
                        else ItemStatus.CANCELLED
                        if status == TurnStatus.CANCELLED
                        else ItemStatus.FAILED
                    )
                    await self.append(
                        session,
                        row,
                        TurnEvent(
                            turnId=row.id, sequence=0, type=EventType.ITEM_UPDATED, item=item
                        ),
                    )
            row.status = status
            row.error = error.model_dump() if error else None
            await self.append(
                session,
                row,
                TurnEvent(
                    turnId=row.id,
                    sequence=0,
                    type=EventType(f"turn_{status}"),
                    status=status,
                    error=error,
                ),
            )

    async def recover_expired(self) -> None:
        async with self.sessions() as session:
            ids = list(
                await session.scalars(
                    select(TurnRecord.id).where(
                        TurnRecord.status == "running", TurnRecord.lease_until < now()
                    )
                )
            )
        for turn_id in ids:
            await self.finish(
                turn_id,
                TurnStatus.INTERRUPTED,
                TurnError(code="ASSISTANT_INTERRUPTED", message="Execution interrupted"),
            )
