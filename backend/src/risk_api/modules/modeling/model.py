from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_api.shared.db import Base


class ModelingDataset(Base):
    __tablename__ = "modeling_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preview: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ModelingExperiment(Base):
    __tablename__ = "modeling_experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("modeling_datasets.id"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    positive_value: Mapped[str] = mapped_column(String(255), nullable=False)
    feature_columns: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coefficients: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
