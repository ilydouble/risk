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
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    in_workbench: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
