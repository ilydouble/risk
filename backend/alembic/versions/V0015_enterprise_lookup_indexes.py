"""Index company identities and names without scanning full financial JSON payloads."""

from alembic import op

revision = "V0015"
down_revision = "V0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX ix_enterprise_company_number ON workbench_enterprise_records
        (dataset_id, (data -> 'properties' ->> 'company_id')) WHERE kind = 'company'
    """)
    op.execute("""
        CREATE INDEX ix_enterprise_name_prefix ON workbench_enterprise_records
        (dataset_id, lower(data ->> 'name') text_pattern_ops) WHERE kind = 'company'
    """)


def downgrade() -> None:
    op.drop_index("ix_enterprise_name_prefix", table_name="workbench_enterprise_records")
    op.drop_index("ix_enterprise_company_number", table_name="workbench_enterprise_records")
