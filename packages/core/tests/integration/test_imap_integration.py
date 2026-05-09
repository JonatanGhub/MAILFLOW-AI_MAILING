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
