"""Shared DTOs used across all core modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ParsedEmail:
    """Refined email data produced by EmailParser."""

    uid: int
    subject_normalized: str
    body_text: str
    body_html: str
    signature: str
    from_email: str
    from_domain: str
    to_emails: list[str] = field(default_factory=list)
    in_reply_to: str | None = None
    thread_id: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying an email through the rule cascade."""

    label: str
    confidence: float
    method: Literal["domain_internal", "domain_client", "thread", "keyword", "llm", "fallback"]
    rule_id: str | None = None


@dataclass(frozen=True)
class DraftRequest:
    """Input for generating and saving a draft reply."""

    in_reply_to_uid: str
    folder: str
    subject: str
    body_text: str
    body_html: str | None
    classification: ClassificationResult
