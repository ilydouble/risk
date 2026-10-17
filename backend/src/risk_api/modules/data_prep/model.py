from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_api.shared.db import Base


class Preparation(Base):
    __tablename__ = "data_preparations"
    __table_args__ = (UniqueConstraint("owner_id", "source_sha", name="uq_preparation_owner_sha"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_sha: Mapped[str] = mapped_column(String(64))
    source: Mapped[bytes] = mapped_column(LargeBinary)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    mapping: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    conversion_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    in_workbench: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PreparationConversion(Base):
    __tablename__ = "data_preparation_conversions"
    __table_args__ = (UniqueConstraint("owner_id", "preparation_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    preparation_id: Mapped[str] = mapped_column(ForeignKey("data_preparations.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(64))
    source_sha: Mapped[str] = mapped_column(String(64))
    mapping_digest: Mapped[str] = mapped_column(String(64))
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    output_sha: Mapped[str] = mapped_column(String(64))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("workbench_datasets.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScriptPreparation(Base):
    __tablename__ = "script_preparations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    preset: Mapped[str] = mapped_column(String(128))
    dataset_key: Mapped[str] = mapped_column(String(128))
    dataset_version: Mapped[str] = mapped_column(String(64))
    source: Mapped[bytes] = mapped_column(LargeBinary)
    source_sha: Mapped[str] = mapped_column(String(64))
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    requirements: Mapped[str] = mapped_column(String(12000), default="")
    script: Mapped[str] = mapped_column(String(100000), default="")
    revision: Mapped[int] = mapped_column(default=1)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScriptPreparationRun(Base):
    __tablename__ = "script_preparation_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("script_preparations.id"), index=True)
    revision: Mapped[int]
    script: Mapped[str] = mapped_column(String(100000))
    script_sha: Mapped[str] = mapped_column(String(64))
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    log: Mapped[str] = mapped_column(String(32000), default="")
    error: Mapped[str] = mapped_column(String(2000), default="")
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary)
    artifact_sha: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
