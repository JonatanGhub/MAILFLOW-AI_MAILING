"""Email provider abstractions for MailFlow.

Each provider implements EmailProvider and encapsulates authentication
and mailbox access for a specific account type.

Available providers (Phase 1):
    - imap      : Generic IMAP server (password auth)
    - microsoft : Microsoft 365 / Outlook (OAuth2 Authorization Code)
    - gmail     : Gmail / Google Workspace (OAuth2)
"""
from .base import EmailProvider

__all__ = ["EmailProvider"]
