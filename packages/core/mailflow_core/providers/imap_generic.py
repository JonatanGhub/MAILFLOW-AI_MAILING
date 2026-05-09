"""IMAP email provider with password authentication."""
from __future__ import annotations

import email
from email.message import Message

import imapclient

from mailflow_core.exceptions import IMAPConnectionError, UIDValidityChanged
from mailflow_core.providers.base import DraftRef, EmailData, EmailProvider

_MAILFLOW_KEYWORD = "MailFlowProcessed"
_MAILFLOW_DRAFT_HEADER = "X-MailFlow-Draft"


def _extract_body(msg: Message) -> tuple[str, str]:
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            charset = part.get_content_charset() or "utf-8"
            if ct == "text/plain" and not body_text:
                body_text = part.get_payload(decode=True).decode(charset, errors="replace")
            elif ct == "text/html" and not body_html:
                body_html = part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        ct = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True).decode(charset, errors="replace")
        if ct == "text/plain":
            body_text = payload
        elif ct == "text/html":
            body_html = payload
    return body_text, body_html


class ImapGenericProvider(EmailProvider):
    """IMAP provider using password authentication via imapclient."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._client: imapclient.IMAPClient | None = None
        self._separator: str = "/"
        self._drafts_folder: str = "Drafts"
        self._uidvalidity: dict[str, int] = {}

    def connect(self) -> None:
        try:
            self._client = imapclient.IMAPClient(
                self._host, port=self._port, use_uid=True, ssl=self._use_ssl
            )
            self._client.login(self._username, self._password)
            self._detect_separator()
            self._detect_drafts_folder()
        except IMAPConnectionError:
            raise
        except Exception as exc:
            raise IMAPConnectionError(str(exc)) from exc

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.logout()
            except Exception:
                pass
            self._client = None

    def keep_alive(self) -> None:
        if self._client:
            self._client.noop()

    def _detect_separator(self) -> None:
        folders = self._client.list_folders()
        if folders:
            _, delimiter, _ = folders[0]
            self._separator = delimiter.decode() if isinstance(delimiter, bytes) else (delimiter or "/")

    def _detect_drafts_folder(self) -> None:
        for flags, _, name in self._client.list_folders():
            str_flags = [f.decode() if isinstance(f, bytes) else f for f in flags]
            if "\\Drafts" in str_flags:
                self._drafts_folder = name
                return

    def _check_uidvalidity(self, folder: str) -> None:
        status = self._client.folder_status(folder, ["UIDVALIDITY"])
        current = int(status[b"UIDVALIDITY"])
        previous = self._uidvalidity.get(folder)
        if previous is not None and previous != current:
            raise UIDValidityChanged(folder, previous, current)
        self._uidvalidity[folder] = current

    def fetch_unprocessed_emails(self, max_count: int = 20) -> list[EmailData]:
        self._client.select_folder("INBOX")
        self._check_uidvalidity("INBOX")
        uids = self._client.search(["NOT", "KEYWORD", _MAILFLOW_KEYWORD])
        uids = uids[:max_count]
        if not uids:
            return []
        raw_messages = self._client.fetch(uids, ["RFC822"])
        result = []
        for uid, data in raw_messages.items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw)
            body_text, body_html = _extract_body(msg)
            refs_str = msg.get("References", "") or ""
            refs = [r.strip() for r in refs_str.split() if r.strip()]
            result.append(
                EmailData(
                    uid=uid,
                    message_id=msg.get("Message-ID", ""),
                    subject=msg.get("Subject", ""),
                    from_email=msg.get("From", ""),
                    to_emails=[msg.get("To", "")],
                    body_text=body_text,
                    body_html=body_html,
                    in_reply_to=msg.get("In-Reply-To"),
                    references=refs,
                    date=msg.get("Date"),
                )
            )
        return result

    def move_email(self, uid: int, destination_folder: str) -> bool:
        self._client.select_folder("INBOX")
        try:
            self._client.copy([uid], destination_folder)
            self._client.store([uid], "+FLAGS", r"\Deleted")
            self._client.expunge()
            return True
        except Exception:
            return False

    def mark_as_processed(self, uid: int) -> None:
        self._client.select_folder("INBOX")
        self._client.store([uid], "+FLAGS", _MAILFLOW_KEYWORD)

    def ensure_folder_exists(self, folder_path: str) -> None:
        parts = folder_path.split(self._separator)
        current = ""
        for part in parts:
            current = f"{current}{self._separator}{part}" if current else part
            if not self._client.folder_exists(current):
                self._client.create_folder(current)

    def find_drafts_in_thread(self, original_message_id: str) -> list[DraftRef]:
        self._client.select_folder(self._drafts_folder)
        uids = self._client.search(["HEADER", "In-Reply-To", original_message_id])
        if not uids:
            return []
        raw_messages = self._client.fetch(uids, ["RFC822", "FLAGS"])
        drafts = []
        for uid, data in raw_messages.items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw)
            drafts.append(
                DraftRef(
                    uid=uid,
                    folder=self._drafts_folder,
                    message_id=msg.get("Message-ID"),
                    in_reply_to=msg.get("In-Reply-To"),
                    has_mailflow_header=_MAILFLOW_DRAFT_HEADER in msg,
                )
            )
        return drafts

    def save_draft(self, message_bytes: bytes) -> bool:
        try:
            self._client.select_folder(self._drafts_folder)
            self._client.append(self._drafts_folder, message_bytes, flags=[r"\Draft"])
            return True
        except Exception:
            return False

    def delete_draft(self, uid: int) -> bool:
        try:
            self._client.select_folder(self._drafts_folder)
            self._client.store([uid], "+FLAGS", r"\Deleted")
            self._client.expunge()
            return True
        except Exception:
            return False
