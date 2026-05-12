"""Modelo ProcessedEmail — registro idempotente de cada email procesado."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"
    __table_args__ = (
        UniqueConstraint("account_id", "uid", "uidvalidity", name="uq_processed_email"),
        Index("ix_processed_email_msg_id", "account_id", "message_id"),
    )

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    uid: Mapped[int] = mapped_column(BigInteger)
    folder: Mapped[str] = mapped_column(String(255))
    uidvalidity: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_email: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String, default="")
    destination_folder: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)
    draft_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("audit_log.cycle_id", ondelete="CASCADE")
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
