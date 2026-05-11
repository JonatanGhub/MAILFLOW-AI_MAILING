"""Modelo AuditLog — registro de cada ciclo de procesamiento."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import UUID as SaUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    cycle_id: Mapped[UUID] = mapped_column(SaUUID(as_uuid=True), unique=True)
    emails_processed: Mapped[int] = mapped_column(Integer, default=0)
    drafts_saved: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
