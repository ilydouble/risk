from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_api.shared.db import Base


class ConversationRecord(Base):
    __tablename__ = "assistant_conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Conversation ID")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, comment="Owner")
    title: Mapped[str] = mapped_column(String(160), comment="Title from first user input")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Last turn activity"
    )


class TurnRecord(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (UniqueConstraint("conversation_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Execution ID")
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_conversations.id"), index=True, comment="Parent conversation"
    )
    request_key: Mapped[str] = mapped_column(String(64), comment="Client idempotency key")
    input_digest: Mapped[str] = mapped_column(String(64), comment="Non-secret request digest")
    status: Mapped[str] = mapped_column(String(24), comment="Execution state")
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, comment="Model settings without key"
    )
    request_id: Mapped[str] = mapped_column(String(128), comment="Gateway correlation ID")
    sequence: Mapped[int] = mapped_column(
        Integer, default=0, comment="Last committed event sequence"
    )
    lease_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="Executor deadline"
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Safe public terminal error"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Turn creation time"
    )


class ItemRecord(Base):
    __tablename__ = "assistant_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Stable display item ID")
    turn_id: Mapped[str] = mapped_column(ForeignKey("assistant_turns.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, comment="First appearance order")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, comment="Latest protocol Item snapshot")


class EventRecord(Base):
    __tablename__ = "assistant_events"
    turn_id: Mapped[str] = mapped_column(ForeignKey("assistant_turns.id"), primary_key=True)
    sequence: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Turn-local replay cursor"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, comment="Framework-independent event v1")
