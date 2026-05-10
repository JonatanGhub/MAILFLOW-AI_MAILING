"""Tests for shared DTOs."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

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
        with pytest.raises(FrozenInstanceError):
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
        with pytest.raises(FrozenInstanceError):
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
        with pytest.raises(FrozenInstanceError):
            req.subject = "other"  # type: ignore[misc]
