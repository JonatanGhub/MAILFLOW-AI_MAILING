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
