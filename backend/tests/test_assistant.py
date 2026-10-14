import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.app import create_app
from risk_api.errors import AppError
from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.model import (
    ConversationRecord,
    EventRecord,
    ItemRecord,
    TurnRecord,
)
from risk_api.modules.assistant.protocol.items import TextItem
from risk_api.modules.assistant.protocol.turns import TurnStatus
from risk_api.modules.assistant.repository import AssistantRepository
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.service import AssistantService
from risk_api.modules.auth.model import User
from risk_api.shared.db import Base


def test_real_strands_stream_and_tool_loop(monkeypatch):
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            deltas = [
                {"reasoning_content": "Check current time."},
                {"content": "I will check."},
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "current_time", "arguments": '{"time'},
                        }
                    ]
                },
                {"tool_calls": [{"index": 0, "function": {"arguments": 'zone":"UTC"}'}}]},
            ]
            stop = "tool_calls"
        else:
            assert any(m["role"] == "tool" for m in payload["messages"])
            deltas = [{"content": "Time checked."}]
            stop = "stop"
        chunks = [
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": d, "finish_reason": None}],
            }
            for d in deltas
        ]
        chunks.append(
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "delta": {}, "finish_reason": stop}],
            }
        )
        body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    async def exercise():
        client = AsyncOpenAI(
            api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        )
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **kwargs: client)
        items = {}
        async for batch in StrandsRuntime().stream(
            "Check time",
            [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "key"),
            "request-1",
        ):
            for item in batch:
                items[item.id] = item
        assert len(requests) == 2
        assert requests[0]["stream"] is True
        assert requests[0]["tools"][0]["function"]["name"] == "current_time"
        assert any(
            i.kind == "reasoning" and i.text == "Check current time." for i in items.values()
        )
        tool = next(i for i in items.values() if i.kind == "tool_call")
        assert tool.status == "completed"
        assert json.loads(tool.argumentsText) == {"timezone": "UTC"}
        assert "UTC" in json.dumps(tool.result)
        assert [i.text for i in items.values() if i.kind == "agent_message"] == [
            "I will check.",
            "Time checked.",
        ]

    asyncio.run(exercise())


def test_persistence_replay_and_execution():
    url = os.environ.get("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for isolated PostgreSQL integration")

    async def exercise():
        schema = f"assistant_test_{uuid4().hex}"
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = AssistantRepository(sessions)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    lambda c: Base.metadata.create_all(
                        c,
                        tables=[
                            User.__table__,
                            ConversationRecord.__table__,
                            TurnRecord.__table__,
                            ItemRecord.__table__,
                            EventRecord.__table__,
                        ],
                    )
                )
            owner, other = str(uuid4()), str(uuid4())
            async with sessions.begin() as session:
                session.add_all(
                    [
                        User(id=u, username=u, password_hash="unused", display_name=u)
                        for u in [owner, other]
                    ]
                )
            conversation = await repo.create_conversation(owner)
            config = ModelSettings("http://model/v1/chat/completions", "test", 1024, "secret")
            turn, created = await repo.start(
                owner, conversation.id, "key", "Hello", config.public(), "r"
            )
            assert created
            repeated, created = await repo.start(
                owner, conversation.id, "key", "Hello", config.public(), "r", accept_new=False
            )
            assert not created and repeated.id == turn.id
            for who, key, message, code in [
                (other, "next", "Hello", "ASSISTANT_NOT_FOUND"),
                (owner, "key", "Changed", "ASSISTANT_KEY_CONFLICT"),
                (owner, "next", "Hello", "ASSISTANT_BUSY"),
            ]:
                with pytest.raises(AppError) as error:
                    await repo.start(who, conversation.id, key, message, config.public(), "r")
                assert error.value.code == code
            with pytest.raises(AppError):
                await repo.events(other, turn.id, 0)
            item = TextItem(kind="agent_message", text="Ans")
            await repo.update_items(turn.id, [item])
            item.text += "wer"
            await repo.update_items(turn.id, [item])
            await repo.finish(turn.id, TurnStatus.COMPLETED)
            events, done = await repo.events(owner, turn.id, 0)
            assert done and events[-1].type == "turn_completed"
            delta = next(e for e in events if e.type == "item_delta")
            assert delta.delta.text == "wer" and delta.item is None
            assert [e.sequence for e in events] == list(range(1, len(events) + 1))
            replay, done = await repo.events(owner, turn.id, 2)
            assert replay == events[2:]
            assert all(i.status == "completed" for i in (await repo.turn(owner, turn.id)).items)
            async with sessions() as session:
                row = await session.get(TurnRecord, turn.id)
                assert "secret" not in json.dumps(row.configuration)
            await repo.finish(turn.id, TurnStatus.CANCELLED)
            assert (await repo.turn(owner, turn.id)).status == "completed"

            expired, _ = await repo.start(
                owner, conversation.id, "expired", "Hi", config.public(), "r"
            )
            async with sessions.begin() as session:
                row = await session.get(TurnRecord, expired.id)
                row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
            assert not await repo.heartbeat(expired.id)
            await repo.recover_expired()
            assert (await repo.turn(owner, expired.id)).status == "interrupted"
            assert not await repo.update_items(
                expired.id, [TextItem(kind="agent_message", text="late")]
            )

            class SlowRuntime(StrandsRuntime):
                async def stream(self, *args):
                    yield [TextItem(kind="reasoning", text="Working")]
                    await asyncio.sleep(60)

            service = AssistantService(repo, SlowRuntime())
            running = await service.start(owner, conversation.id, "cancel", "Hi", config, "r")
            await asyncio.sleep(0.2)
            await service.cancel(owner, running.id)
            await service.close()
            assert (await repo.turn(owner, running.id)).status == "cancelled"
            frames = [frame async for frame in service.events(owner, running.id, 0)]
            assert frames[0].startswith(": connected")
            assert '"type":"turn_cancelled"' in frames[-1]

            class FailedRuntime(StrandsRuntime):
                async def stream(self, *args):
                    yield [TextItem(kind="reasoning", text="Partial")]
                    await asyncio.sleep(0.2)
                    raise RuntimeError("secret upstream body")

            failed_service = AssistantService(repo, FailedRuntime())
            failed = await failed_service.start(
                owner, conversation.id, "failure", "Hi", config, "r"
            )
            await asyncio.gather(*failed_service.tasks.values())
            failed_turn = await repo.turn(owner, failed.id)
            assert failed_turn.status == "failed"
            assert "secret" not in failed_turn.model_dump_json()
            assert failed_turn.items[-1].status == "failed"
            await failed_service.close()
            shutdown_service = AssistantService(repo, SlowRuntime())
            shutdown = await shutdown_service.start(
                owner, conversation.id, "shutdown", "Hi", config, "r"
            )
            await shutdown_service.close()
            assert (await repo.turn(owner, shutdown.id)).status == "interrupted"
            async with sessions() as session:
                assert len(list(await session.scalars(select(EventRecord)))) > 0
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())


def test_protocol_in_openapi():
    app = create_app()
    schema = app.openapi()
    response = schema["paths"]["/api/v1/assistant/turns/events"]["post"]["responses"]["200"]
    assert "text/event-stream" in response["content"]
    assert "application/json" not in response["content"]
    assert "ItemDelta" in schema["components"]["schemas"]
    assert schema["components"]["schemas"]["RequestCreateTurn"]["additionalProperties"] is False
    asyncio.run(app.state.dishka_container.close())
