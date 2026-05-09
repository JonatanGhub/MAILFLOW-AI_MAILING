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
TEST_LOGIN = "test"           # IMAP login (bare username, not email)
TEST_EMAIL = "test@localhost"  # email address for SMTP delivery
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
    msg["To"] = TEST_EMAIL
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id
    with smtplib.SMTP(GREENMAIL_HOST, SMTP_PORT, timeout=5) as smtp:
        smtp.sendmail("sender@external.com", [TEST_EMAIL], msg.as_bytes())


@pytest.fixture(scope="session")
def greenmail_up():
    _wait_for_port(GREENMAIL_HOST, IMAP_PORT)
    _wait_for_port(GREENMAIL_HOST, SMTP_PORT)


@pytest.fixture()
def imap_provider(greenmail_up):
    p = ImapGenericProvider(GREENMAIL_HOST, IMAP_PORT, TEST_LOGIN, TEST_PASS, use_ssl=False)
    p.connect()
    yield p
    p.disconnect()
