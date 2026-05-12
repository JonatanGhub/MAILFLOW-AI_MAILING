# Fase 1 — Core Domain Logic: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four core domain modules (IMAP provider, email parser, rule engine, LLM client) in `packages/core/mailflow_core/` with ≥80% test coverage.

**Architecture:** Shared contracts (types + exceptions) first — Tasks 0–1 are sequential prerequisites. Tasks 2–5 are independent and can run in parallel. Task 6 (integration tests) depends on Task 2.

**Tech Stack:** Python 3.13, imapclient 3.0, email-reply-parser, litellm 1.40, pytest, pytest-mock, greenmail 2.1.2 (Docker)

**Repo root:** `packages/core/` — all paths below are relative to it.

---

## File Map

| File | Action | Task |
|---|---|---|
| `pyproject.toml` | Modify | 0 |
| `../../infrastructure/docker-compose.dev.yml` | Modify | 0 |
| `tests/conftest.py` | Create | 0 |
| `mailflow_core/types.py` | Create | 1 |
| `mailflow_core/exceptions.py` | Create | 1 |
| `mailflow_core/classification/__init__.py` | Create | 1 |
| `mailflow_core/providers/imap_generic.py` | Create | 2 |
| `tests/unit/test_imap_generic.py` | Create | 2 |
| `mailflow_core/email_parser.py` | Create | 3 |
| `tests/unit/test_email_parser.py` | Create | 3 |
| `mailflow_core/classification/rule_engine.py` | Create | 4 |
| `tests/unit/test_rule_engine.py` | Create | 4 |
| `mailflow_core/classification/llm_client.py` | Create | 5 |
| `tests/unit/test_llm_client.py` | Create | 5 |
| `tests/integration/conftest.py` | Create | 6 |
| `tests/integration/test_imap_integration.py` | Create | 6 |

---

## Task 0: Setup — dependencies, Docker, pytest config

**Files:**
- Modify: `pyproject.toml`
- Modify: `../../infrastructure/docker-compose.dev.yml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Update pyproject.toml**

Replace the entire file:

```toml
[project]
name = "mailflow-core"
version = "0.1.0"
description = "MailFlow core domain logic — providers, classification, drafts"
requires-python = ">=3.13"
dependencies = [
    "imapclient>=3.0",
    "email-reply-parser>=0.5",
    "beautifulsoup4>=4.12",
    "pydantic>=2.10",
    "litellm>=1.40",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-cov>=6.0",
    "pytest-mock>=3.14",
    "ruff>=0.8",
    "respx>=0.21",
]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "PLC"]

[tool.pytest.ini_options]
markers = ["integration: requires Docker (greenmail)"]
```

- [ ] **Step 2: Add greenmail to docker-compose.dev.yml**

Open `infrastructure/docker-compose.dev.yml` and add this service inside the `services:` block:

```yaml
  greenmail:
    image: greenmail/standalone:2.1.2
    ports:
      - "3143:3143"   # IMAP
      - "3025:3025"   # SMTP (seed emails in tests)
    environment:
      - GREENMAIL_OPTS=-Dgreenmail.setup.test.all -Dgreenmail.users=test:password:localhost
```

- [ ] **Step 3: Create tests/conftest.py**

```python
"""Root pytest configuration."""
```

- [ ] **Step 4: Install dependencies**

```bash
cd packages/core
uv sync --all-extras
```

Expected: packages installed, no errors.

- [ ] **Step 5: Commit**

```bash
git add packages/core/pyproject.toml infrastructure/docker-compose.dev.yml packages/core/tests/conftest.py
git commit -m "chore: add litellm, respx deps and greenmail to dev stack"
```

---

## Task 1: Shared contracts — types.py + exceptions.py

**Files:**
- Create: `mailflow_core/types.py`
- Create: `mailflow_core/exceptions.py`
- Create: `mailflow_core/classification/__init__.py`

- [ ] **Step 1: Write failing test for types**

Create `tests/unit/test_types.py`:

```python
"""Tests for shared DTOs."""
from __future__ import annotations

import pytest

from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail


class TestParsedEmail:
    def test_immutable(self) -> None:
        email = ParsedEmail(
            uid=1,
            subject_normalized="Hello",
            body_text="Body",
            body_html="",
            signature="",
            from_email="a@b.com",
            from_domain="b.com",
        )
        with pytest.raises(Exception):
            email.uid = 99  # type: ignore[misc]

    def test_defaults(self) -> None:
        email = ParsedEmail(
            uid=1,
            subject_normalized="Hi",
            body_text="",
            body_html="",
            signature="",
            from_email="a@b.com",
            from_domain="b.com",
        )
        assert email.to_emails == []
        assert email.in_reply_to is None
        assert email.thread_id is None
        assert email.date is None


class TestClassificationResult:
    def test_immutable(self) -> None:
        result = ClassificationResult(label="acme", confidence=0.9, method="domain_client")
        with pytest.raises(Exception):
            result.label = "other"  # type: ignore[misc]

    def test_rule_id_defaults_none(self) -> None:
        result = ClassificationResult(label="x", confidence=1.0, method="domain_internal")
        assert result.rule_id is None


class TestDraftRequest:
    def test_immutable(self) -> None:
        cr = ClassificationResult(label="x", confidence=1.0, method="domain_internal")
        req = DraftRequest(
            in_reply_to_uid="1",
            folder="Drafts",
            subject="Re: Hi",
            body_text="Reply",
            body_html=None,
            classification=cr,
        )
        with pytest.raises(Exception):
            req.subject = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_types.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailflow_core.types'`

- [ ] **Step 3: Create mailflow_core/types.py**

```python
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
```

- [ ] **Step 4: Create mailflow_core/exceptions.py**

```python
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
```

- [ ] **Step 5: Create mailflow_core/classification/__init__.py**

```python
"""Email classification — rule engine and LLM client."""
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_types.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add mailflow_core/types.py mailflow_core/exceptions.py mailflow_core/classification/__init__.py tests/unit/test_types.py
git commit -m "feat: add shared DTOs and domain exceptions"
```

---

## Task 2: ImapGenericProvider (unit tests with mocks)

**⚠️ Prerequisite: Task 1 must be complete.**

**Files:**
- Create: `mailflow_core/providers/imap_generic.py`
- Create: `tests/unit/test_imap_generic.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_imap_generic.py`:

```python
"""Unit tests for ImapGenericProvider using mocked imapclient."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from mailflow_core.exceptions import IMAPConnectionError, UIDValidityChanged
from mailflow_core.providers.base import EmailData
from mailflow_core.providers.imap_generic import ImapGenericProvider

# Minimal valid RFC822 bytes for a plain-text email
RAW_EMAIL = (
    b"From: sender@client.com\r\n"
    b"To: me@company.com\r\n"
    b"Subject: Re: Project status\r\n"
    b"Message-ID: <reply@host>\r\n"
    b"In-Reply-To: <original@host>\r\n"
    b"References: <original@host>\r\n"
    b"Date: Fri, 9 May 2026 10:00:00 +0000\r\n"
    b"Content-Type: text/plain\r\n\r\n"
    b"This is the reply body.\r\n\r\nRegards,\r\nSender\r\n"
)

DRAFT_BYTES = (
    b"From: me@company.com\r\n"
    b"In-Reply-To: <original@host>\r\n"
    b"X-MailFlow-Draft: 1\r\n"
    b"Message-ID: <draft@host>\r\n\r\n"
    b"Draft body"
)


@pytest.fixture()
def mock_imap():
    with patch("mailflow_core.providers.imap_generic.imapclient.IMAPClient") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.list_folders.return_value = [([], b"/", "INBOX")]
        instance.folder_status.return_value = {b"UIDVALIDITY": 12345}
        yield instance


@pytest.fixture()
def provider(mock_imap):
    p = ImapGenericProvider("imap.example.com", 993, "user@example.com", "secret")
    p.connect()
    return p


class TestConnect:
    def test_login_called_with_credentials(self, mock_imap):
        p = ImapGenericProvider("imap.example.com", 993, "user@example.com", "secret")
        p.connect()
        mock_imap.login.assert_called_once_with("user@example.com", "secret")

    def test_separator_detected_from_list(self, mock_imap):
        mock_imap.list_folders.return_value = [([], b".", "INBOX")]
        p = ImapGenericProvider("imap.example.com", 993, "u", "p")
        p.connect()
        assert p._separator == "."

    def test_drafts_folder_detected_by_attribute(self, mock_imap):
        mock_imap.list_folders.return_value = [
            ([b"\\Drafts"], b"/", "Borradores"),
            ([], b"/", "INBOX"),
        ]
        p = ImapGenericProvider("imap.example.com", 993, "u", "p")
        p.connect()
        assert p._drafts_folder == "Borradores"

    def test_raises_imap_connection_error_on_failure(self, mock_imap):
        mock_imap.login.side_effect = Exception("Auth failed")
        p = ImapGenericProvider("imap.example.com", 993, "u", "p")
        with pytest.raises(IMAPConnectionError):
            p.connect()


class TestFetchUnprocessedEmails:
    def test_returns_email_list(self, provider, mock_imap):
        mock_imap.search.return_value = [1]
        mock_imap.fetch.return_value = {1: {b"RFC822": RAW_EMAIL}}
        emails = provider.fetch_unprocessed_emails()
        assert len(emails) == 1
        assert isinstance(emails[0], EmailData)
        assert emails[0].uid == 1
        assert emails[0].subject == "Re: Project status"
        assert emails[0].from_email == "sender@client.com"
        assert emails[0].in_reply_to == "<original@host>"
        assert "<original@host>" in emails[0].references

    def test_respects_max_count(self, provider, mock_imap):
        mock_imap.search.return_value = [1, 2, 3, 4, 5]
        mock_imap.fetch.return_value = {i: {b"RFC822": RAW_EMAIL} for i in [1, 2]}
        provider.fetch_unprocessed_emails(max_count=2)
        fetched_uids = mock_imap.fetch.call_args[0][0]
        assert fetched_uids == [1, 2]

    def test_empty_inbox_skips_fetch(self, provider, mock_imap):
        mock_imap.search.return_value = []
        emails = provider.fetch_unprocessed_emails()
        assert emails == []
        mock_imap.fetch.assert_not_called()

    def test_uses_not_keyword_mailflowprocessed(self, provider, mock_imap):
        mock_imap.search.return_value = []
        provider.fetch_unprocessed_emails()
        mock_imap.search.assert_called_once_with(["NOT", "KEYWORD", "MailFlowProcessed"])

    def test_raises_on_uidvalidity_change(self, provider, mock_imap):
        provider._uidvalidity["INBOX"] = 99999
        mock_imap.folder_status.return_value = {b"UIDVALIDITY": 11111}
        with pytest.raises(UIDValidityChanged):
            provider.fetch_unprocessed_emails()


class TestMoveEmail:
    def test_success_returns_true(self, provider, mock_imap):
        result = provider.move_email(1, "Archive")
        assert result is True
        mock_imap.copy.assert_called_once_with([1], "Archive")
        mock_imap.store.assert_called_once_with([1], "+FLAGS", r"\Deleted")
        mock_imap.expunge.assert_called_once()

    def test_no_expunge_when_copy_fails(self, provider, mock_imap):
        mock_imap.copy.side_effect = Exception("COPY failed")
        result = provider.move_email(1, "Archive")
        assert result is False
        mock_imap.expunge.assert_not_called()


class TestMarkAsProcessed:
    def test_stores_mailflow_keyword(self, provider, mock_imap):
        provider.mark_as_processed(42)
        mock_imap.store.assert_called_once_with([42], "+FLAGS", "MailFlowProcessed")


class TestSaveDraft:
    def test_appends_to_drafts_returns_true(self, provider, mock_imap):
        result = provider.save_draft(b"MIME-Version: 1.0\r\n\r\nBody")
        assert result is True
        mock_imap.append.assert_called_once()

    def test_returns_false_on_append_error(self, provider, mock_imap):
        mock_imap.append.side_effect = Exception("APPEND failed")
        result = provider.save_draft(b"bad")
        assert result is False


class TestFindDraftsInThread:
    def test_finds_existing_draft_with_mailflow_header(self, provider, mock_imap):
        mock_imap.search.return_value = [42]
        mock_imap.fetch.return_value = {42: {b"RFC822": DRAFT_BYTES, b"FLAGS": [b"\\Draft"]}}
        drafts = provider.find_drafts_in_thread("<original@host>")
        assert len(drafts) == 1
        assert drafts[0].uid == 42
        assert drafts[0].has_mailflow_header is True

    def test_returns_empty_when_none_found(self, provider, mock_imap):
        mock_imap.search.return_value = []
        drafts = provider.find_drafts_in_thread("<unknown@host>")
        assert drafts == []
        mock_imap.fetch.assert_not_called()


class TestDeleteDraft:
    def test_marks_deleted_and_expunges(self, provider, mock_imap):
        result = provider.delete_draft(42)
        assert result is True
        mock_imap.store.assert_called_with([42], "+FLAGS", r"\Deleted")
        mock_imap.expunge.assert_called_once()

    def test_returns_false_on_error(self, provider, mock_imap):
        mock_imap.store.side_effect = Exception("err")
        result = provider.delete_draft(42)
        assert result is False


class TestEnsureFolderExists:
    def test_creates_missing_folders(self, provider, mock_imap):
        mock_imap.folder_exists.side_effect = [False, False]
        provider.ensure_folder_exists("MailFlow/Clients")
        assert mock_imap.create_folder.call_count == 2

    def test_skips_existing_folder(self, provider, mock_imap):
        mock_imap.folder_exists.return_value = True
        provider.ensure_folder_exists("INBOX")
        mock_imap.create_folder.assert_not_called()


class TestDisconnect:
    def test_logout_called(self, provider, mock_imap):
        provider.disconnect()
        mock_imap.logout.assert_called_once()

    def test_disconnect_when_not_connected_does_not_raise(self):
        p = ImapGenericProvider("host", 993, "u", "p")
        p.disconnect()  # should not raise
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_imap_generic.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailflow_core.providers.imap_generic'`

- [ ] **Step 3: Create mailflow_core/providers/imap_generic.py**

```python
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
        except Exception:
            return False
        self._client.store([uid], "+FLAGS", r"\Deleted")
        self._client.expunge()
        return True

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
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_imap_generic.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mailflow_core/providers/imap_generic.py tests/unit/test_imap_generic.py
git commit -m "feat: implement ImapGenericProvider with unit tests"
```

---

## Task 3: EmailParser

**⚠️ Prerequisite: Task 1 must be complete.**

**Files:**
- Create: `mailflow_core/email_parser.py`
- Create: `tests/unit/test_email_parser.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_email_parser.py`:

```python
"""Tests for EmailParser — subject normalization, signature stripping, thread resolution."""
from __future__ import annotations

import pytest

from mailflow_core.email_parser import EmailParser
from mailflow_core.providers.base import EmailData


def make_email(**kwargs) -> EmailData:
    defaults = dict(
        uid=1,
        message_id="<msg@host>",
        subject="Test",
        from_email="sender@client.com",
        to_emails=["me@company.com"],
        body_text="This is the body.",
        body_html="",
        in_reply_to=None,
        references=[],
        date=None,
    )
    defaults.update(kwargs)
    return EmailData(**defaults)


class TestSubjectNormalization:
    @pytest.mark.parametrize("prefix,expected", [
        ("Re: Meeting notes", "Meeting notes"),
        ("re: Meeting notes", "Meeting notes"),
        ("RE: Meeting notes", "Meeting notes"),
        ("RV: Oferta comercial", "Oferta comercial"),
        ("Fwd: Newsletter", "Newsletter"),
        ("FW: Budget Q1", "Budget Q1"),
        ("Ref: Contract", "Contract"),
        ("AW: Anfrage", "Anfrage"),
        ("TR: Projet", "Projet"),
        ("Re: Fwd: Re: Deep thread", "Deep thread"),
        ("Meeting notes", "Meeting notes"),
        ("", ""),
    ])
    def test_strips_prefix(self, prefix, expected):
        parser = EmailParser()
        parsed = parser.parse(make_email(subject=prefix))
        assert parsed.subject_normalized == expected


class TestFromDomain:
    def test_extracts_domain(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(from_email="user@example.com"))
        assert parsed.from_domain == "example.com"

    def test_lowercases_domain(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(from_email="user@EXAMPLE.COM"))
        assert parsed.from_domain == "example.com"

    def test_no_at_sign_returns_empty(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(from_email="notanemail"))
        assert parsed.from_domain == ""


class TestThreadId:
    def test_first_reference_is_thread_id(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(references=["<root@host>", "<mid@host>"]))
        assert parsed.thread_id == "<root@host>"

    def test_falls_back_to_in_reply_to(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(in_reply_to="<parent@host>", references=[]))
        assert parsed.thread_id == "<parent@host>"

    def test_none_when_no_threading(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(in_reply_to=None, references=[]))
        assert parsed.thread_id is None


class TestBodyParsing:
    def test_body_text_preserved(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(body_text="Hello, this is the message body."))
        assert "Hello, this is the message body." in parsed.body_text

    def test_spanish_saludos_signature_stripped(self):
        parser = EmailParser()
        body = "This is the message.\n\nSaludos,\nJuan García"
        parsed = parser.parse(make_email(body_text=body))
        assert "Saludos" not in parsed.body_text
        assert "Juan" in parsed.signature

    def test_spanish_atentamente_signature_stripped(self):
        parser = EmailParser()
        body = "Please review.\n\nAtentamente,\nMaría López"
        parsed = parser.parse(make_email(body_text=body))
        assert "Atentamente" not in parsed.body_text

    def test_empty_body_text(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(body_text=""))
        assert parsed.body_text == ""
        assert parsed.signature == ""

    def test_uid_preserved(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(uid=42))
        assert parsed.uid == 42

    def test_body_html_preserved(self):
        parser = EmailParser()
        parsed = parser.parse(make_email(body_html="<p>Hello</p>"))
        assert parsed.body_html == "<p>Hello</p>"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_email_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailflow_core.email_parser'`

- [ ] **Step 3: Create mailflow_core/email_parser.py**

```python
"""Parses and refines EmailData into ParsedEmail."""
from __future__ import annotations

import re

from email_reply_parser import EmailReplyParser

from mailflow_core.providers.base import EmailData
from mailflow_core.types import ParsedEmail

_SUBJECT_PREFIX = re.compile(
    r"^\s*(re|rv|fwd|fw|ref|aw|tr)\s*:\s*",
    re.IGNORECASE,
)

_SPANISH_SIGNATURE = re.compile(
    r"\n(saludos|atentamente|un saludo|gracias|atento saludo)[,\s]",
    re.IGNORECASE,
)


def _normalize_subject(subject: str) -> str:
    prev = None
    while prev != subject:
        prev = subject
        subject = _SUBJECT_PREFIX.sub("", subject)
    return subject.strip()


def _strip_signature(body_text: str) -> tuple[str, str]:
    parsed = EmailReplyParser.parse_reply(body_text)
    if parsed.strip() != body_text.strip():
        signature = body_text[len(parsed):].strip()
        return parsed.strip(), signature
    match = _SPANISH_SIGNATURE.search(body_text)
    if match:
        return body_text[: match.start()].strip(), body_text[match.start():].strip()
    return body_text.strip(), ""


class EmailParser:
    """Refines EmailData: normalizes subject, strips signature, resolves thread ID."""

    def parse(self, email_data: EmailData) -> ParsedEmail:
        subject_normalized = _normalize_subject(email_data.subject)
        body_text, signature = _strip_signature(email_data.body_text)
        parts = email_data.from_email.split("@")
        from_domain = parts[-1].lower() if len(parts) >= 2 else ""
        thread_id: str | None = None
        if email_data.references:
            thread_id = email_data.references[0]
        elif email_data.in_reply_to:
            thread_id = email_data.in_reply_to
        return ParsedEmail(
            uid=email_data.uid,
            subject_normalized=subject_normalized,
            body_text=body_text,
            body_html=email_data.body_html,
            signature=signature,
            from_email=email_data.from_email,
            from_domain=from_domain,
            to_emails=email_data.to_emails,
            in_reply_to=email_data.in_reply_to,
            thread_id=thread_id,
            date=email_data.date,
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_email_parser.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mailflow_core/email_parser.py tests/unit/test_email_parser.py
git commit -m "feat: implement EmailParser with subject normalization and signature stripping"
```

---

## Task 4: RuleEngine

**⚠️ Prerequisite: Task 1 must be complete.**

**Files:**
- Create: `mailflow_core/classification/rule_engine.py`
- Create: `tests/unit/test_rule_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_rule_engine.py`:

```python
"""Tests for RuleEngine classification cascade."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mailflow_core.classification.rule_engine import (
    AccountConfig,
    DomainRule,
    KeywordRule,
    RuleEngine,
)
from mailflow_core.types import ClassificationResult, ParsedEmail


def make_email(**kwargs) -> ParsedEmail:
    defaults = dict(
        uid=1,
        subject_normalized="Project proposal",
        body_text="Please review the attached proposal.",
        body_html="",
        signature="",
        from_email="contact@acmecorp.com",
        from_domain="acmecorp.com",
        to_emails=["me@company.com"],
        in_reply_to=None,
        thread_id=None,
        date=None,
    )
    defaults.update(kwargs)
    return ParsedEmail(**defaults)


def base_config(**kwargs) -> AccountConfig:
    defaults = dict(
        account_id="acc-1",
        internal_domains=["company.com"],
        client_domain_rules=[
            DomainRule(domain="acmecorp.com", label="acme", rule_id="rule-1"),
        ],
        keyword_rules=[
            KeywordRule(keywords=["urgent", "asap"], label="priority", rule_id="kw-1"),
        ],
    )
    defaults.update(kwargs)
    return AccountConfig(**defaults)


class TestStep1InternalDomain:
    def test_internal_domain_confidence_1(self):
        engine = RuleEngine(base_config())
        result = engine.classify(make_email(from_domain="company.com"))
        assert result.label == "internal"
        assert result.confidence == 1.0
        assert result.method == "domain_internal"


class TestStep2ClientDomain:
    def test_known_client_domain(self):
        engine = RuleEngine(base_config())
        result = engine.classify(make_email(from_domain="acmecorp.com"))
        assert result.label == "acme"
        assert result.confidence == 0.95
        assert result.method == "domain_client"
        assert result.rule_id == "rule-1"

    @pytest.mark.parametrize("domain", [
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
        "yahoo.es", "icloud.com", "me.com", "protonmail.com",
        "proton.me", "live.com",
    ])
    def test_generic_domains_not_matched_as_client(self, domain):
        config = base_config(
            client_domain_rules=[DomainRule(domain=domain, label="generic", rule_id="r1")]
        )
        engine = RuleEngine(config)
        result = engine.classify(make_email(from_domain=domain))
        assert result.method != "domain_client"


class TestStep3ThreadInheritance:
    def test_inherits_from_most_recent_high_confidence(self):
        engine = RuleEngine(base_config())
        history = [
            ClassificationResult(label="acme", confidence=0.95, method="domain_client"),
        ]
        result = engine.classify(make_email(from_domain="unknown.net"), thread_history=history)
        assert result.label == "acme"
        assert result.confidence == 0.90
        assert result.method == "thread"

    def test_does_not_inherit_when_last_is_low_confidence(self):
        engine = RuleEngine(base_config())
        history = [ClassificationResult(label="acme", confidence=0.50, method="llm")]
        result = engine.classify(make_email(from_domain="unknown.net"), thread_history=history)
        assert result.method != "thread"

    def test_inherits_from_last_entry(self):
        engine = RuleEngine(base_config())
        history = [
            ClassificationResult(label="old", confidence=0.95, method="domain_client"),
            ClassificationResult(label="new", confidence=0.85, method="llm"),
        ]
        result = engine.classify(make_email(from_domain="unknown.net"), thread_history=history)
        assert result.label == "new"


class TestStep4Keywords:
    def test_or_match_first_keyword(self):
        engine = RuleEngine(base_config())
        result = engine.classify(make_email(from_domain="unknown.net", subject_normalized="URGENT request"))
        assert result.label == "priority"
        assert result.confidence == 0.80
        assert result.method == "keyword"

    def test_or_match_second_keyword(self):
        engine = RuleEngine(base_config())
        result = engine.classify(make_email(from_domain="unknown.net", body_text="we need this asap"))
        assert result.label == "priority"

    def test_and_match_requires_all_keywords(self):
        config = base_config(
            keyword_rules=[
                KeywordRule(keywords=["invoice", "overdue"], label="finance", rule_id="kw-2", match_all=True)
            ]
        )
        engine = RuleEngine(config)
        result = engine.classify(make_email(from_domain="unknown.net", body_text="The invoice is overdue."))
        assert result.label == "finance"

    def test_and_match_partial_does_not_match(self):
        config = base_config(
            keyword_rules=[
                KeywordRule(keywords=["invoice", "overdue"], label="finance", rule_id="kw-2", match_all=True)
            ]
        )
        engine = RuleEngine(config)
        result = engine.classify(make_email(from_domain="unknown.net", body_text="The invoice is pending."))
        assert result.method != "keyword"

    def test_keyword_case_insensitive(self):
        engine = RuleEngine(base_config())
        result = engine.classify(make_email(from_domain="unknown.net", subject_normalized="URGENT matter"))
        assert result.method == "keyword"


class TestStep5LLMFallback:
    def test_uses_llm_when_no_rule_matches(self):
        mock_llm = MagicMock()
        mock_llm.classify.return_value = ClassificationResult(label="acme", confidence=0.75, method="llm")
        engine = RuleEngine(base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm)
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "llm"
        assert result.label == "acme"

    def test_low_confidence_llm_falls_to_fallback(self):
        mock_llm = MagicMock()
        mock_llm.classify.return_value = ClassificationResult(label="maybe", confidence=0.40, method="llm")
        engine = RuleEngine(base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm)
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "fallback"

    def test_llm_exception_falls_to_fallback(self):
        mock_llm = MagicMock()
        mock_llm.classify.side_effect = Exception("LLM unavailable")
        engine = RuleEngine(base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm)
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "fallback"


class TestStep6Fallback:
    def test_fallback_when_no_rules_and_no_llm(self):
        engine = RuleEngine(AccountConfig(account_id="empty"))
        result = engine.classify(make_email(from_domain="totally.unknown"))
        assert result.label == "unclassified"
        assert result.confidence == 0.0
        assert result.method == "fallback"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_rule_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailflow_core.classification.rule_engine'`

- [ ] **Step 3: Create mailflow_core/classification/rule_engine.py**

```python
"""Deterministic classification cascade for incoming emails."""
from __future__ import annotations

from dataclasses import dataclass, field

from mailflow_core.types import ClassificationResult, ParsedEmail

GENERIC_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.es",
    "icloud.com", "me.com", "protonmail.com", "proton.me", "live.com",
})


@dataclass(frozen=True)
class DomainRule:
    domain: str
    label: str
    rule_id: str


@dataclass(frozen=True)
class KeywordRule:
    keywords: list[str]
    label: str
    rule_id: str
    match_all: bool = False


@dataclass
class AccountConfig:
    account_id: str
    internal_domains: list[str] = field(default_factory=list)
    client_domain_rules: list[DomainRule] = field(default_factory=list)
    keyword_rules: list[KeywordRule] = field(default_factory=list)


class RuleEngine:
    """Six-step classification cascade: domain → thread → keyword → LLM → fallback."""

    def __init__(self, config: AccountConfig, llm_client: object | None = None) -> None:
        self._config = config
        self._llm = llm_client

    def classify(
        self,
        email: ParsedEmail,
        thread_history: list[ClassificationResult] | None = None,
        available_labels: list[str] | None = None,
    ) -> ClassificationResult:
        labels = available_labels or [r.label for r in self._config.client_domain_rules] + ["unclassified"]

        # Step 1: internal domain
        if email.from_domain in self._config.internal_domains:
            return ClassificationResult(label="internal", confidence=1.0, method="domain_internal")

        # Step 2: known client domain (skip generic providers)
        if email.from_domain not in GENERIC_DOMAINS:
            for rule in self._config.client_domain_rules:
                if rule.domain == email.from_domain:
                    return ClassificationResult(
                        label=rule.label, confidence=0.95, method="domain_client", rule_id=rule.rule_id
                    )

        # Step 3: thread inheritance (most recent entry)
        if thread_history:
            last = thread_history[-1]
            if last.confidence >= 0.80:
                return ClassificationResult(label=last.label, confidence=0.90, method="thread")

        # Step 4: keyword match
        search_text = f"{email.subject_normalized} {email.body_text}".lower()
        for rule in self._config.keyword_rules:
            kws = [k.lower() for k in rule.keywords]
            matched = all(k in search_text for k in kws) if rule.match_all else any(k in search_text for k in kws)
            if matched:
                return ClassificationResult(
                    label=rule.label, confidence=0.80, method="keyword", rule_id=rule.rule_id
                )

        # Step 5: LLM fallback
        if self._llm is not None:
            try:
                result = self._llm.classify(email, available_labels=labels)
                if result.confidence >= 0.60:
                    return result
            except Exception:
                pass

        # Step 6: unclassified
        return ClassificationResult(label="unclassified", confidence=0.0, method="fallback")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_rule_engine.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mailflow_core/classification/rule_engine.py tests/unit/test_rule_engine.py
git commit -m "feat: implement RuleEngine with six-step classification cascade"
```

---

## Task 5: LLMClient

**⚠️ Prerequisite: Task 1 must be complete.**

**Files:**
- Create: `mailflow_core/classification/llm_client.py`
- Create: `tests/unit/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_llm_client.py`:

```python
"""Tests for LLMClient — classify and generate_draft via litellm."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mailflow_core.classification.llm_client import LLMClient, LLMConfig
from mailflow_core.exceptions import ClassificationError, LLMError
from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail


def cfg(**kwargs) -> LLMConfig:
    defaults = dict(model_id="ollama/llama3", api_base="http://localhost:11434")
    defaults.update(kwargs)
    return LLMConfig(**defaults)


def make_email(**kwargs) -> ParsedEmail:
    defaults = dict(
        uid=1, subject_normalized="Invoice due", body_text="Please send the invoice.",
        body_html="", signature="", from_email="client@acme.com", from_domain="acme.com",
        to_emails=["me@co.com"], in_reply_to=None, thread_id=None, date=None,
    )
    defaults.update(kwargs)
    return ParsedEmail(**defaults)


def make_request(**kwargs) -> DraftRequest:
    cr = ClassificationResult(label="acme", confidence=0.95, method="domain_client")
    defaults = dict(
        in_reply_to_uid="1", folder="Drafts", subject="Re: Invoice due",
        body_text="Here is the invoice.", body_html=None, classification=cr,
    )
    defaults.update(kwargs)
    return DraftRequest(**defaults)


def fake_completion(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


class TestClassify:
    def test_valid_response_returns_result(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion(json.dumps({"label": "acme", "confidence": 0.88}))
            result = client.classify(make_email(), available_labels=["acme", "internal"])
        assert result.label == "acme"
        assert result.confidence == 0.88
        assert result.method == "llm"

    def test_invalid_json_raises_classification_error(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion("not json")
            with pytest.raises(ClassificationError):
                client.classify(make_email(), available_labels=["acme"])

    def test_label_not_in_available_raises_classification_error(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion(json.dumps({"label": "unknown", "confidence": 0.9}))
            with pytest.raises(ClassificationError):
                client.classify(make_email(), available_labels=["acme", "internal"])

    def test_missing_confidence_key_raises_classification_error(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion(json.dumps({"label": "acme"}))
            with pytest.raises(ClassificationError):
                client.classify(make_email(), available_labels=["acme"])

    def test_llm_exception_raises_llm_error(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.side_effect = Exception("connection refused")
            with pytest.raises(LLMError):
                client.classify(make_email(), available_labels=["acme"])

    def test_api_base_passed_to_litellm(self):
        client = LLMClient(cfg(api_base="http://custom:11434"))
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion(json.dumps({"label": "acme", "confidence": 0.9}))
            client.classify(make_email(), available_labels=["acme"])
        call_kwargs = mock_c.call_args[1]
        assert call_kwargs["api_base"] == "http://custom:11434"


class TestGenerateDraft:
    def test_returns_body_text(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.return_value = fake_completion("Here is our reply to your request.")
            result = client.generate_draft(make_email(), make_request())
        assert result == "Here is our reply to your request."

    def test_llm_error_propagates(self):
        client = LLMClient(cfg())
        with patch("mailflow_core.classification.llm_client.litellm.completion") as mock_c:
            mock_c.side_effect = Exception("timeout")
            with pytest.raises(LLMError):
                client.generate_draft(make_email(), make_request())
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/unit/test_llm_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailflow_core.classification.llm_client'`

- [ ] **Step 3: Create mailflow_core/classification/llm_client.py**

```python
"""LiteLLM wrapper for email classification and draft generation."""
from __future__ import annotations

import json
from dataclasses import dataclass

import litellm

from mailflow_core.exceptions import ClassificationError, LLMError
from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail

_CLASSIFY_SYSTEM = (
    "You are an email classification assistant. "
    "Given an email, classify it into exactly one of the provided labels. "
    'Respond ONLY with a JSON object: {"label": "<label>", "confidence": <0.0-1.0>}. '
    "The label must be one of the provided options. No other text."
)

_DRAFT_SYSTEM = (
    "You are a professional email drafting assistant. "
    "Write a reply in the same language as the original email. "
    "Return only the body text — no subject line, no headers, no signature placeholder."
)


@dataclass
class LLMConfig:
    model_id: str
    api_base: str | None = None
    api_key: str | None = None
    timeout: float = 30.0
    max_retries: int = 2


class LLMClient:
    """Wrapper around litellm.completion for classify and generate_draft."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def _call(self, messages: list[dict]) -> str:
        kwargs: dict = {
            "model": self._config.model_id,
            "messages": messages,
            "timeout": self._config.timeout,
            "num_retries": self._config.max_retries,
        }
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    def classify(self, email: ParsedEmail, available_labels: list[str]) -> ClassificationResult:
        user_msg = (
            f"Labels: {', '.join(available_labels)}\n\n"
            f"Subject: {email.subject_normalized}\n"
            f"From: {email.from_email}\n\n"
            f"{email.body_text[:500]}"
        )
        raw = self._call([
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
        try:
            data = json.loads(raw)
            label = data["label"]
            confidence = float(data["confidence"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ClassificationError(f"Invalid LLM response: {raw!r}") from exc
        if label not in available_labels:
            raise ClassificationError(f"Label {label!r} not in available labels: {available_labels}")
        return ClassificationResult(label=label, confidence=confidence, method="llm")

    def generate_draft(self, original_email: ParsedEmail, request: DraftRequest) -> str:
        user_msg = (
            f"Original email:\nSubject: {original_email.subject_normalized}\n"
            f"From: {original_email.from_email}\n\n"
            f"{original_email.body_text[:500]}\n\n"
            f"Classification: {request.classification.label}\n"
            f"Reply subject: {request.subject}"
        )
        return self._call([
            {"role": "system", "content": _DRAFT_SYSTEM},
            {"role": "user", "content": user_msg},
        ])
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_llm_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mailflow_core/classification/llm_client.py tests/unit/test_llm_client.py
git commit -m "feat: implement LLMClient wrapper for classification and draft generation"
```

---

## Task 6: Integration tests (greenmail)

**⚠️ Prerequisite: Task 2 must be complete. Requires Docker.**

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_imap_integration.py`

- [ ] **Step 1: Start greenmail**

```bash
docker compose -f infrastructure/docker-compose.dev.yml up -d greenmail
```

Expected: container `greenmail` running, ports 3143 and 3025 open.

- [ ] **Step 2: Create tests/integration/__init__.py**

```python
```

- [ ] **Step 3: Create tests/integration/conftest.py**

```python
"""Pytest fixtures for IMAP integration tests against greenmail."""
from __future__ import annotations

import smtplib
import socket
import time
from email.mime.text import MIMEText

import pytest

from mailflow_core.providers.imap_generic import ImapGenericProvider

GREENMAIL_HOST = "localhost"
IMAP_PORT = 3143
SMTP_PORT = 3025
TEST_USER = "test@localhost"
TEST_PASS = "password"


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Port {host}:{port} did not open within {timeout}s")


def send_smtp(subject: str, body: str, message_id: str | None = None) -> None:
    msg = MIMEText(body)
    msg["From"] = "sender@external.com"
    msg["To"] = TEST_USER
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id
    with smtplib.SMTP(GREENMAIL_HOST, SMTP_PORT, timeout=5) as smtp:
        smtp.sendmail("sender@external.com", [TEST_USER], msg.as_bytes())


@pytest.fixture(scope="session")
def greenmail_up():
    _wait_for_port(GREENMAIL_HOST, IMAP_PORT)
    _wait_for_port(GREENMAIL_HOST, SMTP_PORT)


@pytest.fixture()
def imap_provider(greenmail_up):
    p = ImapGenericProvider(GREENMAIL_HOST, IMAP_PORT, TEST_USER, TEST_PASS, use_ssl=False)
    p.connect()
    yield p
    p.disconnect()
```

- [ ] **Step 4: Create tests/integration/test_imap_integration.py**

```python
"""Integration tests for ImapGenericProvider against greenmail."""
from __future__ import annotations

import time

import pytest

from tests.integration.conftest import send_smtp

pytestmark = pytest.mark.integration


class TestFetchAndMark:
    def test_fetches_new_email(self, imap_provider):
        send_smtp("Integration hello", "Body text", message_id="<hello@greenmail>")
        time.sleep(0.5)
        emails = imap_provider.fetch_unprocessed_emails()
        assert any(e.subject == "Integration hello" for e in emails)

    def test_mark_as_processed_excludes_from_next_fetch(self, imap_provider):
        send_smtp("To be marked", "Mark me")
        time.sleep(0.5)
        emails = imap_provider.fetch_unprocessed_emails()
        target = next((e for e in emails if e.subject == "To be marked"), None)
        assert target is not None
        imap_provider.mark_as_processed(target.uid)
        after = imap_provider.fetch_unprocessed_emails()
        assert all(e.uid != target.uid for e in after)


class TestDraftLifecycle:
    def test_save_find_delete_draft(self, imap_provider):
        draft_bytes = (
            b"From: me@localhost\r\n"
            b"In-Reply-To: <thread-abc@host>\r\n"
            b"X-MailFlow-Draft: 1\r\n"
            b"Message-ID: <draft-abc@host>\r\n\r\n"
            b"Draft reply body"
        )
        assert imap_provider.save_draft(draft_bytes) is True
        time.sleep(0.3)
        found = imap_provider.find_drafts_in_thread("<thread-abc@host>")
        assert len(found) >= 1
        assert found[0].has_mailflow_header is True
        draft_uid = found[0].uid
        assert imap_provider.delete_draft(draft_uid) is True


class TestMoveEmail:
    def test_move_to_archive(self, imap_provider):
        send_smtp("Move me", "Body")
        time.sleep(0.5)
        emails = imap_provider.fetch_unprocessed_emails()
        target = next((e for e in emails if e.subject == "Move me"), None)
        assert target is not None
        imap_provider.ensure_folder_exists("Archive")
        result = imap_provider.move_email(target.uid, "Archive")
        assert result is True
```

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest tests/integration/ -v -m integration
```

Expected: all integration tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/
git commit -m "test: add IMAP integration tests against greenmail"
```

---

## Task 7: Coverage check and lint

- [ ] **Step 1: Run full test suite (unit only)**

```bash
uv run pytest packages/core/tests/unit/ --cov=mailflow_core --cov-report=term-missing --cov-fail-under=80 -v
```

Expected: coverage ≥ 80%, all tests GREEN.

- [ ] **Step 2: Run linter**

```bash
uv run ruff check packages/core/
```

Expected: no errors. If errors appear, run `uv run ruff format packages/core/` then fix any remaining lint issues.

- [ ] **Step 3: Run with integration tests (requires Docker)**

```bash
uv run pytest packages/core/tests/ --cov=mailflow_core --cov-fail-under=80 -v
```

Expected: coverage higher than unit-only run, all tests GREEN.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify coverage ≥80% across core domain modules"
```

---

## Parallel execution note

After Task 1 is complete, Tasks 2, 3, 4, and 5 are fully independent — they touch different files and share only the types defined in Task 1. They can be dispatched as four parallel subagents. Task 6 depends on Task 2.

Recommended dispatch order:
1. Task 0 → Task 1 (sequential, ~15 min total)
2. Tasks 2, 3, 4, 5 in parallel (~20 min)
3. Task 6 (after Task 2 completes, ~10 min)
4. Task 7 (after all complete, ~5 min)
