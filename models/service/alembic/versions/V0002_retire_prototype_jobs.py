"""Fence prototype executions before switching to the model-owned CLI."""

from alembic import op

revision = "V0002"
down_revision = "V0001"


def upgrade() -> None:
    op.execute(
        "UPDATE attempts SET status='cancelled', error='Retired execution protocol', "
        "finished_at=now() "
        "WHERE status='running'"
    )
    op.execute(
        "UPDATE jobs SET status='cancelled', cancel_requested=true, "
        "lease_owner=NULL, lease_until=NULL, "
        "error='Retired execution protocol' WHERE status IN ('queued','running')"
    )


def downgrade() -> None:
    pass  # Retired jobs are intentionally not restarted by a schema rollback.
