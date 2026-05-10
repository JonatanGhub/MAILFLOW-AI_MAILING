"""Tests for the abstract EmailProvider interface and EmailData DTO."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mailflow_core.providers.base import DraftRef, EmailData, EmailProvider


class _ConcreteProvider(EmailProvider):
    """Minimal concrete implementation for testing the abstract interface."""

    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def keep_alive(self) -> None:
        pass

    def fetch_unprocessed_emails(self, max_count: int = 20) -> list[EmailData]:
        return []

    def move_email(self, uid: int, destination_folder: str) -> bool:
        return True

    def mark_as_processed(self, uid: int) -> None:
        pass

    def ensure_folder_exists(self, folder_path: str) -> None:
        pass

    def find_drafts_in_thread(self, original_message_id: str) -> list[DraftRef]:
        return []

    def save_draft(self, message_bytes: bytes) -> bool:
        return True

    def delete_draft(self, uid: int) -> bool:
        return True


class TestEmailDataDTO:
    def test_immutable(self) -> None:
        data = EmailData(
            uid=1,
            message_id="<id@host>",
            subject="Test",
            from_email="a@b.com",
            to_emails=["c@d.com"],
            body_text="Hello",
            body_html="<p>Hello</p>",
        )
        with pytest.raises(FrozenInstanceError):
            data.uid = 99  # type: ignore[misc]

    def test_defaults(self) -> None:
        data = EmailData(
            uid=1,
            message_id="<id@host>",
            subject="Subject",
            from_email="a@b.com",
            to_emails=[],
            body_text="",
            body_html="",
        )
        assert data.in_reply_to is None
        assert data.references == []
        assert data.date is None


class TestEmailProviderContextManager:
    def test_connect_on_enter(self) -> None:
        provider = _ConcreteProvider()
        assert not provider.connected
        with provider:
            assert provider.connected
        assert not provider.connected

    def test_disconnect_on_exit(self) -> None:
        provider = _ConcreteProvider()
        with provider:
            pass
        assert not provider.connected


class TestDraftRef:
    def test_immutable(self) -> None:
        ref = DraftRef(uid=1, folder="Drafts", message_id="<x>", in_reply_to=None)
        with pytest.raises(FrozenInstanceError):
            ref.uid = 99  # type: ignore[misc]

    def test_default_has_mailflow_header(self) -> None:
        ref = DraftRef(uid=1, folder="Drafts", message_id=None, in_reply_to=None)
        assert ref.has_mailflow_header is False
