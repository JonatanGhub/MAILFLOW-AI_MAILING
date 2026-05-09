"""Domain exceptions for MailFlow core."""

from __future__ import annotations


class MailFlowError(Exception):
    """Base exception for all MailFlow domain errors."""


class IMAPConnectionError(MailFlowError):
    """Raised when IMAP connection or authentication fails."""


class UIDValidityChanged(MailFlowError):
    """Raised when UIDVALIDITY changes for a folder — cache must be invalidated."""

    def __init__(self, folder: str, old: int, new: int) -> None:
        self.folder = folder
        self.old = old
        self.new = new
        super().__init__(f"UIDVALIDITY changed for {folder!r}: {old} -> {new}")


class DraftCollisionError(MailFlowError):
    """Raised when a MailFlow draft already exists for the same thread (ADR-004)."""


class LLMError(MailFlowError):
    """Raised when the LLM call fails after all retries."""


class ClassificationError(MailFlowError):
    """Raised when the LLM response cannot be parsed into a ClassificationResult."""
