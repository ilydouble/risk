"""Persistent Agent conversations, items and replayable events."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0009"
down_revision = "V0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        Column("id", String(64), primary_key=True, comment="Conversation ID"),
        Column("owner_id", String(64), ForeignKey("users.id"), nullable=False, comment="Owner"),
        Column("title", String(160), nullable=False, comment="Title from first input"),
        Column(
            "updated_at",
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            comment="Last activity",
        ),
    )
    op.create_index("ix_assistant_conversations_owner_id", "assistant_conversations", ["owner_id"])
    op.create_table(
        "assistant_turns",
        Column("id", String(64), primary_key=True, comment="Execution ID"),
        Column(
            "conversation_id",
            String(64),
            ForeignKey("assistant_conversations.id"),
            nullable=False,
            comment="Parent conversation",
        ),
        Column("request_key", String(64), nullable=False, comment="Client idempotency key"),
        Column("input_digest", String(64), nullable=False, comment="Non-secret input digest"),
        Column("status", String(24), nullable=False, comment="Execution state"),
        Column("configuration", JSONB, nullable=False, comment="Model settings excluding key"),
        Column("request_id", String(128), nullable=False, comment="Gateway request ID"),
        Column("sequence", Integer, nullable=False, comment="Last committed event sequence"),
        Column("lease_until", DateTime(timezone=True), nullable=False, comment="Executor deadline"),
        Column("error", JSONB, nullable=True, comment="Safe terminal error"),
        Column(
            "created_at",
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            comment="Turn creation time",
        ),
        UniqueConstraint("conversation_id", "request_key"),
    )
    op.create_index("ix_assistant_turns_conversation_id", "assistant_turns", ["conversation_id"])
    op.create_table(
        "assistant_items",
        Column("id", String(64), primary_key=True, comment="Stable item ID"),
        Column(
            "turn_id",
            String(64),
            ForeignKey("assistant_turns.id"),
            nullable=False,
            comment="Owning turn",
        ),
        Column("position", Integer, nullable=False, comment="First appearance order"),
        Column("payload", JSONB, nullable=False, comment="Current protocol item"),
    )
    op.create_index("ix_assistant_items_turn_id", "assistant_items", ["turn_id"])
    op.create_table(
        "assistant_events",
        Column(
            "turn_id",
            String(64),
            ForeignKey("assistant_turns.id"),
            primary_key=True,
            comment="Owning turn",
        ),
        Column("sequence", Integer, primary_key=True, comment="Turn-local replay cursor"),
        Column("payload", JSONB, nullable=False, comment="Protocol event v1"),
    )


def downgrade() -> None:
    for table in (
        "assistant_events",
        "assistant_items",
        "assistant_turns",
        "assistant_conversations",
    ):
        op.drop_table(table)
