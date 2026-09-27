"""Upgrade modeling workbench for Bundle v1 and durable jobs.

Revision ID: V0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0003"
down_revision = "V0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("modeling_datasets", "status", type_=sa.String(24))
    op.add_column(
        "modeling_datasets",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("modeling_datasets", sa.Column("task_type", sa.String(32)))
    op.add_column("modeling_datasets", sa.Column("sample_unit", sa.String(32)))
    op.add_column("modeling_datasets", sa.Column("manifest", JSONB()))
    op.add_column(
        "modeling_datasets",
        sa.Column("capabilities", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "modeling_datasets",
        sa.Column("validation", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "modeling_datasets",
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("modeling_datasets", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("modeling_datasets", sa.Column("finished_at", sa.DateTime(timezone=True)))

    op.alter_column("modeling_experiments", "status", type_=sa.String(24))
    op.add_column("modeling_experiments", sa.Column("target_name", sa.String(128)))
    op.add_column(
        "modeling_experiments",
        sa.Column(
            "selected_features",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "modeling_experiments",
        sa.Column(
            "requested_models",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "modeling_experiments",
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "modeling_experiments",
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "modeling_experiments",
        sa.Column("artifacts", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("modeling_experiments", sa.Column("error", sa.Text()))
    op.add_column("modeling_experiments", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("modeling_experiments", sa.Column("finished_at", sa.DateTime(timezone=True)))

    op.create_table(
        "modeling_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "dataset_id", sa.String(64), sa.ForeignKey("modeling_datasets.id"), nullable=False
        ),
        sa.Column(
            "experiment_id", sa.String(64), sa.ForeignKey("modeling_experiments.id")
        ),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_modeling_jobs_owner_id", "modeling_jobs", ["owner_id"])
    op.create_index("ix_modeling_jobs_dataset_id", "modeling_jobs", ["dataset_id"])
    op.create_index("ix_modeling_jobs_experiment_id", "modeling_jobs", ["experiment_id"])
    op.create_index(
        "ix_modeling_jobs_claim", "modeling_jobs", ["status", "lease_until", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("modeling_jobs")
    for column in (
        "finished_at",
        "started_at",
        "error",
        "artifacts",
        "results",
        "progress",
        "requested_models",
        "selected_features",
        "target_name",
    ):
        op.drop_column("modeling_experiments", column)
    op.alter_column("modeling_experiments", "status", type_=sa.String(16))
    for column in (
        "finished_at",
        "started_at",
        "progress",
        "validation",
        "capabilities",
        "manifest",
        "sample_unit",
        "task_type",
        "schema_version",
    ):
        op.drop_column("modeling_datasets", column)
    op.alter_column("modeling_datasets", "status", type_=sa.String(16))
