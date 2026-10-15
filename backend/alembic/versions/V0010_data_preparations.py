"""Persist source cases, reports and confirmed mapping handoffs."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0010"
down_revision = "V0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_preparations",
        Column("id", String(64), primary_key=True),
        Column("owner_id", String(64), ForeignKey("users.id"), nullable=False),
        Column("filename", String(255), nullable=False),
        Column("source_sha", String(64), nullable=False),
        Column("source", LargeBinary, nullable=False),
        Column("profile", JSONB, nullable=False),
        Column("report", JSONB, nullable=True),
        Column("mapping", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        Column("confirmed", Boolean, nullable=False, server_default=text("false")),
        Column("in_workbench", Boolean, nullable=False, server_default=text("false")),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        UniqueConstraint("owner_id", "source_sha", name="uq_preparation_owner_sha"),
    )
    op.create_index("ix_data_preparations_owner_id", "data_preparations", ["owner_id"])
    op.add_column("workbench_datasets", Column("source_preparation_id", String(64), nullable=True))
    op.add_column("workbench_datasets", Column(
        "mapping_snapshot", JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    ))


def downgrade() -> None:
    op.drop_column("workbench_datasets", "mapping_snapshot")
    op.drop_column("workbench_datasets", "source_preparation_id")
    op.drop_table("data_preparations")
