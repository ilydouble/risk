"""Initial relational schema.

Revision ID: V0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name_cn", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("reg_no", sa.String(128), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("sector", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("credit_score", sa.Integer(), nullable=False),
        sa.Column("summary", JSONB(), nullable=False),
        sa.Column("profile", JSONB(), nullable=False),
        sa.Column("scores", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_companies_region_sector_risk", "companies", ["region", "sector", "risk_level"]
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("company_id", sa.String(64), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_company", "documents", ["company_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("companies")
    op.drop_table("users")
