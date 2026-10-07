"""Independent model execution records."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0001"
down_revision = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column(
            "id", sa.String(64), primary_key=True, comment="Business operation idempotency ID"
        ),
        sa.Column("kind", sa.String(32), nullable=False, comment="validate or train"),
        sa.Column("payload", JSONB, nullable=False, comment="Immutable execution input"),
        sa.Column("status", sa.String(24), nullable=False, comment="Authoritative execution state"),
        sa.Column("stage", sa.String(32), nullable=False, comment="Current computation phase"),
        sa.Column("attempt", sa.Integer, nullable=False, comment="Number of execution attempts"),
        sa.Column("lease_owner", sa.String(64), comment="Attempt fencing token"),
        sa.Column("lease_until", sa.DateTime(timezone=True), comment="Worker lease expiry"),
        sa.Column(
            "cancel_requested", sa.Boolean, nullable=False, comment="Durable cancellation intent"
        ),
        sa.Column(
            "result", JSONB, nullable=False, comment="Validated output and artifact references"
        ),
        sa.Column("error", sa.Text, comment="Failure diagnostic"),
        sa.Column(
            "request_id", sa.String(128), nullable=False, comment="Initial HTTP correlation ID"
        ),
        sa.Column(
            "next_event", sa.Integer, nullable=False, comment="Last allocated event sequence"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Submission time",
        ),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_table(
        "attempts",
        sa.Column("id", sa.String(64), primary_key=True, comment="Lease fencing token"),
        sa.Column(
            "job_id", sa.String(64), sa.ForeignKey("jobs.id"), nullable=False, comment="Parent job"
        ),
        sa.Column("number", sa.Integer, nullable=False, comment="Attempt ordinal"),
        sa.Column("status", sa.String(24), nullable=False, comment="Attempt outcome"),
        sa.Column("error", sa.Text, comment="Attempt diagnostic"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Claim time",
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), comment="Completion or expiry time"),
        sa.UniqueConstraint("job_id", "number"),
    )
    op.create_index("ix_attempts_job_id", "attempts", ["job_id"])
    op.create_table(
        "events",
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("jobs.id"),
            primary_key=True,
            comment="Parent job",
        ),
        sa.Column("sequence", sa.Integer, primary_key=True, comment="Per-job replay cursor"),
        sa.Column("attempt", sa.Integer, nullable=False, comment="Originating attempt"),
        sa.Column("kind", sa.String(24), nullable=False, comment="state, metric or log"),
        sa.Column("data", JSONB, nullable=False, comment="Structured event payload"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Event creation time",
        ),
    )


def downgrade():
    op.drop_table("events")
    op.drop_table("attempts")
    op.drop_table("jobs")
