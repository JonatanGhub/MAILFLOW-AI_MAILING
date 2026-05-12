"""Modelos DomainRule, KeywordRule, InternalDomain.

IMPORTANTE — colisión de nombres:
  Estos son los modelos SQLAlchemy (ORM).
  En packages/core/mailflow_core/classification/rule_engine.py existen
  dataclasses homónimas. Importar con alias:
    from app.models.rules import DomainRule as DbDomainRule
    from mailflow_core.classification.rule_engine import DomainRule as CoreDomainRule
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class DomainRule(Base):
    __tablename__ = "domain_rules"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    domain: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class KeywordRule(Base):
    __tablename__ = "keyword_rules"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String))
    label: Mapped[str] = mapped_column(String(255))
    rule_id: Mapped[str] = mapped_column(String(100))
    match_all: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class InternalDomain(Base):
    __tablename__ = "internal_domains"

    id: Mapped[UUID] = uuid_pk()
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE")
    )
    domain: Mapped[str] = mapped_column(String(255))
