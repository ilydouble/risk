"""Persist executable plans and immutable trial artifacts."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0011"
down_revision = "V0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_preparations",
        sa.Column(
            "conversion_plan",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_table(
        "data_preparation_conversions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "preparation_id", sa.String(64), sa.ForeignKey("data_preparations.id"), nullable=False
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("source_sha", sa.String(64), nullable=False),
        sa.Column("mapping_digest", sa.String(64), nullable=False),
        sa.Column("plan", JSONB, nullable=False),
        sa.Column("output", JSONB, nullable=False),
        sa.Column("output_sha", sa.String(64), nullable=False),
        sa.Column("report", JSONB, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("workbench_datasets.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("owner_id", "preparation_id", "fingerprint"),
    )
    op.create_index(
        "ix_data_preparation_conversions_owner_id", "data_preparation_conversions", ["owner_id"]
    )
    op.create_index(
        "ix_data_preparation_conversions_preparation_id",
        "data_preparation_conversions",
        ["preparation_id"],
    )


def downgrade() -> None:
    op.drop_table("data_preparation_conversions")
    op.drop_column("data_preparations", "conversion_plan")
