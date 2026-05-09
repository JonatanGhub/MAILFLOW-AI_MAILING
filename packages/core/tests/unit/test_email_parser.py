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
