"""Unit tests for ImapGenericProvider using mocked imapclient."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mailflow_core.exceptions import IMAPConnectionError, UIDValidityChanged
from mailflow_core.providers.base import EmailData
from mailflow_core.providers.imap_generic import ImapGenericProvider

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
        p.disconnect()
