"""Business ownership records; model execution lives in the independent service."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_api.shared.db import Base


class Dataset(Base):
    __tablename__ = "workbench_datasets"
    source_preparation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    protocol_generation: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2", comment="Workbench execution contract generation"
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Run(Base):
    __tablename__ = "workbench_runs"
    protocol_generation: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2", comment="Workbench execution contract generation"
    )
    __table_args__ = (UniqueConstraint("owner_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("workbench_datasets.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    request_key: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB)
    retry_of: Mapped[str | None] = mapped_column(ForeignKey("workbench_runs.id"))
    execution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "workbench_model_versions"
    protocol_generation: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2", comment="Workbench execution contract generation"
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workbench_runs.id"), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    artifact: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dispatch(Base):
    __tablename__ = "workbench_dispatch"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    request_id: Mapped[str] = mapped_column(String(128))
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnterpriseImport(Base):
    __tablename__ = "workbench_enterprise_imports"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("workbench_datasets.id"), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnterpriseRecord(Base):
    __tablename__ = "workbench_enterprise_records"
    __table_args__ = (
        UniqueConstraint("dataset_id", "snapshot", "node_id"),
        Index("ix_enterprise_source", "dataset_id", "snapshot", "source"),
        Index("ix_enterprise_target", "dataset_id", "snapshot", "target"),
        Index(
            "uq_enterprise_company",
            "dataset_id",
            "node_id",
            unique=True,
            postgresql_where=text("kind = 'company'"),
        ),
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("workbench_enterprise_imports.dataset_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    snapshot: Mapped[str] = mapped_column(Text)
    node_id: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    members: Mapped[list[str]] = mapped_column(JSONB)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


class EnterprisePrediction(Base):
    __tablename__ = "workbench_enterprise_predictions"
    model_id: Mapped[str] = mapped_column(
        ForeignKey("workbench_model_versions.id"), primary_key=True
    )
    company_id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("workbench_datasets.id"), index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
