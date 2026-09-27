"""Add modeling workbench datasets and experiments.

Revision ID: V0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0002"
down_revision = "V0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modeling_datasets",
        sa.Column("id", sa.String(64), primary_key=True, comment="数据集唯一标识"),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="创建数据集的用户标识",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="数据集显示名称"),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True, comment="对象存储键"),
        sa.Column("filename", sa.String(255), nullable=False, comment="原始文件名"),
        sa.Column("content_type", sa.String(128), nullable=False, comment="文件 MIME 类型"),
        sa.Column("size", sa.Integer(), nullable=False, comment="文件字节数"),
        sa.Column("status", sa.String(16), nullable=False, comment="pending、ready 或 failed"),
        sa.Column("row_count", sa.Integer(), comment="分析后的有效数据行数"),
        sa.Column("column_count", sa.Integer(), comment="分析后的字段数"),
        sa.Column("analysis", JSONB(), comment="字段画像与质量报告"),
        sa.Column("preview", JSONB(), comment="受限数据预览"),
        sa.Column("error", sa.Text(), comment="解析失败原因"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="创建时间",
        ),
    )
    op.create_index("ix_modeling_datasets_owner_id", "modeling_datasets", ["owner_id"])
    op.create_table(
        "modeling_experiments",
        sa.Column("id", sa.String(64), primary_key=True, comment="实验唯一标识"),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("modeling_datasets.id"),
            nullable=False,
            comment="输入数据集标识",
        ),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="创建实验的用户标识",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="实验显示名称"),
        sa.Column("model_type", sa.String(64), nullable=False, comment="模型类型"),
        sa.Column("status", sa.String(16), nullable=False, comment="实验状态"),
        sa.Column("target_column", sa.String(255), nullable=False, comment="二分类目标字段"),
        sa.Column("positive_value", sa.String(255), nullable=False, comment="正类原始值"),
        sa.Column("feature_columns", JSONB(), nullable=False, comment="入模字段列表"),
        sa.Column("configuration", JSONB(), nullable=False, comment="训练与切分配置"),
        sa.Column("metrics", JSONB(), nullable=False, comment="训练集与测试集指标"),
        sa.Column("coefficients", JSONB(), nullable=False, comment="标准化特征系数"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="创建时间",
        ),
    )
    op.create_index(
        "ix_modeling_experiments_dataset_id", "modeling_experiments", ["dataset_id"]
    )
    op.create_index("ix_modeling_experiments_owner_id", "modeling_experiments", ["owner_id"])


def downgrade() -> None:
    op.drop_table("modeling_experiments")
    op.drop_table("modeling_datasets")
