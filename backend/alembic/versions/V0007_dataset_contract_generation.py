"""Invalidate the prototype workbench without deleting its records or objects."""

import sqlalchemy as sa

from alembic import op

revision = "V0007"
down_revision = "V0006"


def upgrade() -> None:
    for table in ("workbench_datasets", "workbench_runs", "workbench_model_versions"):
        op.add_column(
            table,
            sa.Column(
                "protocol_generation",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment="Workbench execution contract generation",
            ),
        )
        op.alter_column(table, "protocol_generation", server_default="2")
    op.execute(
        "UPDATE workbench_dispatch SET delivered=true, error='Retired workbench protocol' "
        "WHERE NOT delivered"
    )


def downgrade() -> None:
    # Downgrading schema does not requeue previously invalidated deliveries.
    for table in ("workbench_model_versions", "workbench_runs", "workbench_datasets"):
        op.drop_column(table, "protocol_generation")
