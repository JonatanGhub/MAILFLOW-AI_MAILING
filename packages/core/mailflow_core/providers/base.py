"""Abstract EmailProvider interface.

All concrete providers (IMAP, Microsoft, Gmail) must implement this interface.
The API and worker depend only on this abstraction — never on concrete classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailData:
    """Parsed email data transfer object."""

    uid: int
    message_id: str
    subject: str
    from_email: str
    to_emails: list[str]
    body_text: str
    body_html: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    date: str | None = None


@dataclass(frozen=True)
class DraftRef:
    """Reference to a draft saved in the IMAP Drafts folder."""

    uid: int
    folder: str
    message_id: str | None
    in_reply_to: str | None
    has_mailflow_header: bool = False


class EmailProvider(ABC):
    """Abstract base class for all email provider implementations.

    Implementations must be context-manager compatible for connection lifecycle.
    All operations use UIDs (not sequence numbers).
    """

    @abstractmethod
    def connect(self) -> None:
        """Authenticate and open the IMAP connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Logout and close the IMAP connection."""

    def __enter__(self) -> EmailProvider:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()

    @abstractmethod
    def keep_alive(self) -> None:
        """Send a NOOP to keep the connection alive."""

    @abstractmethod
    def fetch_unprocessed_emails(self, max_count: int = 20) -> list[EmailData]:
        """Fetch unprocessed emails from INBOX, FIFO order (ADR-012).

        Uses SEARCH NOT KEYWORD MailFlowProcessed to filter.
        """

    @abstractmethod
    def move_email(self, uid: int, destination_folder: str) -> bool:
        """Move email using safe COPY -> STORE \\Deleted -> EXPUNGE sequence.

        Returns True on success. If COPY fails, EXPUNGE is NOT called.
        """

    @abstractmethod
    def mark_as_processed(self, uid: int) -> None:
        """Set the MailFlowProcessed keyword flag on a message."""

    @abstractmethod
    def ensure_folder_exists(self, folder_path: str) -> None:
        """Create folder hierarchy level by level if it does not exist."""

    @abstractmethod
    def find_drafts_in_thread(self, original_message_id: str) -> list[DraftRef]:
        """Find existing drafts in the Drafts folder referencing this thread.

        Prevents duplicate drafts per ADR-004.
        """

    @abstractmethod
    def save_draft(self, message_bytes: bytes) -> bool:
        """Append a draft to the IMAP Drafts folder with the \\Draft flag."""

    @abstractmethod
    def delete_draft(self, uid: int) -> bool:
        """Delete a draft by UID from the Drafts folder."""
