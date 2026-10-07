"""Business records for the independent RiskGNN service; legacy tables remain intact."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0006"
down_revision = "V0005"


def upgrade():
    op.create_table(
        "workbench_datasets",
        sa.Column("id", sa.String(64), primary_key=True, comment="Business record identity"),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="Owning user",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="Dataset display name"),
        sa.Column("filename", sa.String(255), nullable=False, comment="Original archive name"),
        sa.Column(
            "object_key",
            sa.String(512),
            nullable=False,
            unique=True,
            comment="Upload staging object",
        ),
        sa.Column("content_type", sa.String(128), nullable=False, comment="Upload content type"),
        sa.Column("size", sa.Integer, nullable=False, comment="Declared compressed size"),
        sa.Column(
            "confirmed", sa.Boolean, nullable=False, comment="Upload completion acknowledged"
        ),
        sa.Column("execution", JSONB, nullable=False, comment="Last observed model-service state"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Creation time",
        ),
    )
    op.create_index("ix_workbench_datasets_owner_id", "workbench_datasets", ["owner_id"])
    op.create_table(
        "workbench_runs",
        sa.Column("id", sa.String(64), primary_key=True, comment="Business record identity"),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="Owning user",
        ),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("workbench_datasets.id"),
            nullable=False,
            comment="Bound dataset",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="Experiment display name"),
        sa.Column(
            "request_key", sa.String(64), nullable=False, comment="User-scoped idempotency key"
        ),
        sa.Column("configuration", JSONB, nullable=False, comment="Frozen training configuration"),
        sa.Column(
            "retry_of",
            sa.String(64),
            sa.ForeignKey("workbench_runs.id"),
            nullable=True,
            comment="Previous run being repeated",
        ),
        sa.Column("execution", JSONB, nullable=False, comment="Last observed model-service state"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Creation time",
        ),
        sa.UniqueConstraint("owner_id", "request_key"),
    )
    op.create_index("ix_workbench_runs_owner_id", "workbench_runs", ["owner_id"])
    op.create_index("ix_workbench_runs_dataset_id", "workbench_runs", ["dataset_id"])
    op.create_table(
        "workbench_model_versions",
        sa.Column("id", sa.String(64), primary_key=True, comment="Business record identity"),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="Owning user",
        ),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("workbench_runs.id"),
            nullable=False,
            unique=True,
            comment="Independently tested source run",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="Published version name"),
        sa.Column(
            "artifact", JSONB, nullable=False, comment="Immutable artifact digest and report"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Creation time",
        ),
    )
    op.create_index(
        "ix_workbench_model_versions_owner_id", "workbench_model_versions", ["owner_id"]
    )
    op.create_table(
        "workbench_dispatch",
        sa.Column("id", sa.String(64), primary_key=True, comment="Delivery identity"),
        sa.Column("operation", sa.String(24), nullable=False, comment="submit or cancel"),
        sa.Column("payload", JSONB, nullable=False, comment="Immutable internal request"),
        sa.Column(
            "request_id", sa.String(128), nullable=False, comment="Initial request correlation ID"
        ),
        sa.Column("delivered", sa.Boolean, nullable=False, comment="Delivery acknowledged"),
        sa.Column("attempts", sa.Integer, nullable=False, comment="Delivery attempt count"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Next delivery time",
        ),
        sa.Column("error", sa.Text, comment="Last delivery failure"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Enqueue time",
        ),
    )
    op.create_index("ix_workbench_dispatch_delivered", "workbench_dispatch", ["delivered"])


def downgrade():
    op.drop_table("workbench_dispatch")
    op.drop_table("workbench_model_versions")
    op.drop_table("workbench_runs")
    op.drop_table("workbench_datasets")
