"""Record authoritative Turn completion time without inventing legacy durations."""

import sqlalchemy as sa

from alembic import op

revision = "V0010"
down_revision = "V0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_turns",
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Time the server finalized the Turn; unknown for legacy rows",
        ),
    )
    op.add_column(
        "assistant_turns",
        sa.Column(
            "duration_ms",
            sa.BigInteger(),
            nullable=True,
            comment="Elapsed milliseconds from creation to finalization; null if unknown",
        ),
    )


def downgrade() -> None:
    op.drop_column("assistant_turns", "duration_ms")
    op.drop_column("assistant_turns", "finished_at")
