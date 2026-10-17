"""Persist script workspaces and frozen execution artifacts."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0013"
down_revision = "V0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_preparations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("preset", sa.String(128), nullable=False),
        sa.Column("dataset_key", sa.String(128), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("source", sa.LargeBinary(), nullable=False),
        sa.Column("source_sha", sa.String(64), nullable=False),
        sa.Column("files", JSONB, nullable=False),
        sa.Column("requirements", sa.String(12000), nullable=False),
        sa.Column("script", sa.String(100000), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("messages", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_index("ix_script_preparations_owner_id", "script_preparations", ["owner_id"])
    op.create_table(
        "script_preparation_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.String(64),
                  sa.ForeignKey("script_preparations.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("script", sa.String(100000), nullable=False),
        sa.Column("script_sha", sa.String(64), nullable=False),
        sa.Column("specification", JSONB, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("log", sa.String(32000), nullable=False),
        sa.Column("error", sa.String(2000), nullable=False),
        sa.Column("result", JSONB, nullable=False),
        sa.Column("artifact", sa.LargeBinary()),
        sa.Column("artifact_sha", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_script_preparation_runs_owner_id", "script_preparation_runs", ["owner_id"])
    op.create_index("ix_script_preparation_runs_task_id", "script_preparation_runs", ["task_id"])


def downgrade() -> None:
    op.drop_table("script_preparation_runs")
    op.drop_table("script_preparations")
