"""Add imported aggregate overview snapshots.

Revision ID: V0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0004"
down_revision = "V0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "overview_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dataset_name", sa.String(255), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("overview_snapshots")
