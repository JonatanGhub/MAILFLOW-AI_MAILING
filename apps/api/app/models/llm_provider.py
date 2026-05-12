"""Modelo LLMProvider — configuración de proveedor LLM por organización."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[UUID] = uuid_pk()
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(
        String(50)
    )  # 'ollama'|'openai'|'anthropic'|'custom'
    base_url: Mapped[str] = mapped_column(String(500))
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    default_classification_model: Mapped[str] = mapped_column(String(200))
    default_generation_model: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
