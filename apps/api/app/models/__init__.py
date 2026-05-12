"""Re-exports para que Alembic pueda descubrir todos los modelos via Base.metadata."""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.email_account import EmailAccount
from app.models.llm_provider import LLMProvider
from app.models.organization import Organization
from app.models.processed_email import ProcessedEmail
from app.models.rules import DomainRule, InternalDomain, KeywordRule

__all__ = [
    "Base",
    "AuditLog",
    "DomainRule",
    "EmailAccount",
    "InternalDomain",
    "KeywordRule",
    "LLMProvider",
    "Organization",
    "ProcessedEmail",
]
