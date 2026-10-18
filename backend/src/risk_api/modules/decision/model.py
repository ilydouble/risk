from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_api.shared.db import Base


class DeployedFinancialModel(Base):
    __tablename__ = "deployed_financial_models"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(128), unique=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    descriptor: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialPrediction(Base):
    __tablename__ = "financial_predictions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_key", name="uq_financial_prediction_request"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("deployed_financial_models.id"))
    dataset_id: Mapped[str | None] = mapped_column(
        ForeignKey("workbench_datasets.id", ondelete="SET NULL"), index=True
    )
    request_key: Mapped[str] = mapped_column(String(64))
    request_sha256: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(128))
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_serialized: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
