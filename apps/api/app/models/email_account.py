"""Modelo EmailAccount — cuenta de email gestionada por MailFlow."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk
from app.models.llm_provider import LLMProvider


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[UUID] = uuid_pk()
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    provider_type: Mapped[str] = mapped_column(String(20), default="imap")
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[str] = mapped_column(String(255))
    encrypted_credentials: Mapped[str] = mapped_column(String)
    inbox_folder: Mapped[str] = mapped_column(String(255), default="INBOX")
    unclassified_folder: Mapped[str] = mapped_column(
        String(255), default="Sin_Clasificar"
    )
    drafts_folder: Mapped[str] = mapped_column(String(255), default="Drafts")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_cycle_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    llm_provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Nunca auto-loaded; usar selectinload explícito en AccountRepository.get_full_config
    llm_provider: Mapped[LLMProvider | None] = relationship(
        "LLMProvider",
        foreign_keys=[llm_provider_id],
        lazy="noload",
    )
