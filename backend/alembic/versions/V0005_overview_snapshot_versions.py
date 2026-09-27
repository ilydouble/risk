"""Allow multiple derived snapshots from one source archive.

Revision ID: V0005
"""

from alembic import op

revision = "V0005"
down_revision = "V0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "overview_snapshots_source_sha256_key",
        "overview_snapshots",
        type_="unique",
    )
    op.create_index(
        "ix_overview_snapshots_source_sha256",
        "overview_snapshots",
        ["source_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_overview_snapshots_source_sha256",
        table_name="overview_snapshots",
    )
    op.create_unique_constraint(
        "overview_snapshots_source_sha256_key",
        "overview_snapshots",
        ["source_sha256"],
    )
