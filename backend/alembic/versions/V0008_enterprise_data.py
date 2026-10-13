"""Owner-scoped normalized enterprise snapshots and model predictions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "V0008"
down_revision = "V0007"


def upgrade() -> None:
    op.create_table(
        "workbench_enterprise_imports",
        sa.Column(
            "dataset_id", sa.String(64), sa.ForeignKey("workbench_datasets.id"), primary_key=True
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "workbench_enterprise_records",
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("workbench_enterprise_imports.dataset_id"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("node_id", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("target", sa.Text()),
        sa.Column("members", postgresql.JSONB(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("dataset_id", "snapshot", "node_id"),
    )
    op.create_index(
        "ix_workbench_enterprise_records_kind", "workbench_enterprise_records", ["kind"]
    )
    op.create_index(
        "ix_enterprise_source", "workbench_enterprise_records", ["dataset_id", "snapshot", "source"]
    )
    op.create_index(
        "ix_enterprise_target", "workbench_enterprise_records", ["dataset_id", "snapshot", "target"]
    )
    op.create_index(
        "uq_enterprise_company",
        "workbench_enterprise_records",
        ["dataset_id", "node_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'company'"),
    )
    op.create_table(
        "workbench_enterprise_predictions",
        sa.Column(
            "model_id",
            sa.String(64),
            sa.ForeignKey("workbench_model_versions.id"),
            primary_key=True,
        ),
        sa.Column("company_id", sa.Text(), primary_key=True),
        sa.Column(
            "dataset_id", sa.String(64), sa.ForeignKey("workbench_datasets.id"), nullable=False
        ),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_workbench_enterprise_predictions_dataset_id",
        "workbench_enterprise_predictions",
        ["dataset_id"],
    )


def downgrade() -> None:
    op.drop_table("workbench_enterprise_predictions")
    op.drop_table("workbench_enterprise_records")
    op.drop_table("workbench_enterprise_imports")
