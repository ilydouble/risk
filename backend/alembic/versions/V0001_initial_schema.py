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
        sa.Column("id", sa.String(64), primary_key=True, comment="用户唯一标识"),
        sa.Column("username", sa.String(128), nullable=False, unique=True, comment="登录用户名"),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="Argon2 密码哈希"),
        sa.Column("display_name", sa.String(128), nullable=False, comment="界面显示名称"),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.String(64), primary_key=True, comment="企业唯一标识"),
        sa.Column("name_cn", sa.String(255), nullable=False, comment="企业中文名称"),
        sa.Column("name_en", sa.String(255), nullable=False, comment="企业英文名称"),
        sa.Column("reg_no", sa.String(128), nullable=False, comment="企业注册编号"),
        sa.Column("region", sa.String(128), nullable=False, comment="所属地区，用于检索筛选"),
        sa.Column("sector", sa.String(128), nullable=False, comment="所属行业，用于检索筛选"),
        sa.Column("risk_level", sa.String(16), nullable=False, comment="演示风险等级"),
        sa.Column("credit_score", sa.Integer(), nullable=False, comment="演示信用评分"),
        sa.Column("summary", JSONB(), nullable=False, comment="企业列表与画像头部的摘要快照"),
        sa.Column("profile", JSONB(), nullable=False, comment="企业画像详情快照"),
        sa.Column("scores", JSONB(), nullable=False, comment="按语言保存的演示评分与解释快照"),
    )
    op.create_index(
        "ix_companies_region_sector_risk", "companies", ["region", "sector", "risk_level"]
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True, comment="文件记录唯一标识"),
        sa.Column(
            "company_id",
            sa.String(64),
            sa.ForeignKey("companies.id"),
            nullable=False,
            comment="所属企业标识",
        ),
        sa.Column(
            "object_key", sa.String(512), nullable=False, unique=True, comment="对象存储中的对象键"
        ),
        sa.Column("filename", sa.String(255), nullable=False, comment="上传文件名"),
        sa.Column("content_type", sa.String(128), nullable=False, comment="文件的 MIME 类型"),
        sa.Column("size", sa.Integer(), nullable=False, comment="预期文件大小，单位字节"),
        sa.Column("status", sa.String(16), nullable=False, comment="上传状态：pending 或 ready"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            comment="文件记录创建时间",
        ),
    )
    op.create_index("ix_documents_company", "documents", ["company_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("companies")
    op.drop_table("users")
