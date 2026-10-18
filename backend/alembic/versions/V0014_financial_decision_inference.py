"""Register deployed financial models and owner-bound prediction history."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "V0014"
down_revision = "V0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployed_financial_models",
        sa.Column("id", sa.String(64), primary_key=True, comment="由模型清单摘要确定的部署模型 ID"),
        sa.Column(
            "model_version",
            sa.String(128),
            nullable=False,
            unique=True,
            comment="不可变的发布模型版本名，不关联本地训练 Run",
        ),
        sa.Column(
            "manifest_sha256",
            sa.String(64),
            nullable=False,
            unique=True,
            comment="完整模型包 manifest 的 SHA-256",
        ),
        sa.Column("descriptor", JSONB, nullable=False, comment="模型身份、输入协议与校准状态快照"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="首次登记时间",
        ),
    )
    op.create_table(
        "financial_predictions",
        sa.Column("id", sa.String(64), primary_key=True, comment="预测记录唯一 ID"),
        sa.Column(
            "owner_id",
            sa.String(64),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="有权访问该预测的账号",
        ),
        sa.Column(
            "model_id",
            sa.String(64),
            sa.ForeignKey("deployed_financial_models.id"),
            nullable=False,
            comment="实际使用的已部署模型版本",
        ),
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("workbench_datasets.id", ondelete="SET NULL"),
            comment="企业输入的数据集；显式输入为空，数据集删除后保留预测快照",
        ),
        sa.Column("request_key", sa.String(64), nullable=False, comment="账号范围内的幂等请求键"),
        sa.Column(
            "request_sha256",
            sa.String(64),
            nullable=False,
            comment="提交参数摘要，用于拒绝幂等键冲突",
        ),
        sa.Column("request_id", sa.String(128), nullable=False, comment="网关传递的日志关联 ID"),
        sa.Column("source", JSONB, nullable=False, comment="企业、观测期、来源摘要或显式输入说明"),
        sa.Column(
            "input_snapshot", JSONB, nullable=False, comment="实际参与评分的冻结特征，不含监督标签"
        ),
        sa.Column(
            "input_serialized",
            sa.Text(),
            nullable=False,
            comment="实际输入的精确 JSON 字符串，保留 JSONB 无法保留的特征顺序",
        ),
        sa.Column(
            "result", JSONB, nullable=False, comment="原始/校准候选分数、设备、精度与模型限制"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="预测完成并持久化的时间",
        ),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_financial_prediction_request"),
    )
    op.create_index("ix_financial_predictions_owner_id", "financial_predictions", ["owner_id"])
    op.create_index("ix_financial_predictions_dataset_id", "financial_predictions", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("financial_predictions")
    op.drop_table("deployed_financial_models")
