"""Tests unitarios para _build_llm_client y _build_draft_bytes."""
from __future__ import annotations

import email as email_module
from unittest.mock import MagicMock, patch

# ── _build_draft_bytes ───────────────────────────────────────────────────────

def test_build_draft_bytes_returns_valid_rfc2822():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="Question about invoice",
        from_email="worker@company.com",
        to_email="sender@client.com",
        body_text="Thank you for your email.",
        in_reply_to="<msg-123@client.com>",
    )

    assert isinstance(result, bytes)
    msg = email_module.message_from_bytes(result)
    assert msg["Subject"] == "Re: Question about invoice"
    assert msg["From"] == "worker@company.com"
    assert msg["To"] == "sender@client.com"
    assert msg["In-Reply-To"] == "<msg-123@client.com>"
    assert msg["References"] == "<msg-123@client.com>"
    payload = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
    assert "Thank you for your email." in payload


def test_build_draft_bytes_no_double_re_prefix():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="Re: Already prefixed",
        from_email="a@b.com",
        to_email="c@d.com",
        body_text="Body",
    )
    msg = email_module.message_from_bytes(result)
    assert msg["Subject"] == "Re: Already prefixed"


def test_build_draft_bytes_no_in_reply_to():
    from app.services.cycle import _build_draft_bytes

    result = _build_draft_bytes(
        subject="New topic",
        from_email="a@b.com",
        to_email="c@d.com",
        body_text="Hello",
    )
    msg = email_module.message_from_bytes(result)
    assert msg["In-Reply-To"] is None
    assert msg["References"] is None


# ── _build_llm_client ────────────────────────────────────────────────────────

def test_build_llm_client_returns_none_for_none_provider():
    from app.services.cycle import _build_llm_client

    assert _build_llm_client(None, for_generation=True) is None


def test_build_llm_client_returns_none_for_inactive_provider():
    from app.services.cycle import _build_llm_client

    mock_provider = MagicMock()
    mock_provider.is_active = False
    assert _build_llm_client(mock_provider, for_generation=True) is None


def test_build_llm_client_generation_uses_generation_model():
    from app.services.cycle import _build_llm_client
    from mailflow_core.classification.llm_client import LLMClient

    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = None
    provider.base_url = "http://localhost:11434"
    provider.default_generation_model = "ollama/llama3"
    provider.default_classification_model = "ollama/llama3:8b"

    client = _build_llm_client(provider, for_generation=True)

    assert isinstance(client, LLMClient)
    assert client._config.model_id == "ollama/llama3"
    assert client._config.api_base == "http://localhost:11434"
    assert client._config.api_key is None


def test_build_llm_client_classify_uses_classification_model():
    from app.services.cycle import _build_llm_client
    from mailflow_core.classification.llm_client import LLMClient

    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = None
    provider.base_url = "http://localhost:11434"
    provider.default_generation_model = "ollama/llama3"
    provider.default_classification_model = "ollama/llama3:8b"

    client = _build_llm_client(provider, for_generation=False)

    assert isinstance(client, LLMClient)
    assert client._config.model_id == "ollama/llama3:8b"


def test_build_llm_client_decrypts_api_key():
    from app.crypto import encrypt
    from app.services.cycle import _build_llm_client
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    provider = MagicMock()
    provider.is_active = True
    provider.encrypted_api_key = encrypt({"api_key": "sk-test-123"}, key)
    provider.base_url = "https://api.openai.com"
    provider.default_generation_model = "gpt-4o"
    provider.default_classification_model = "gpt-4o-mini"

    with patch("app.services.cycle.settings") as mock_settings:
        mock_settings.SECRET_KEY = key
        client = _build_llm_client(provider, for_generation=True)

    assert client._config.api_key == "sk-test-123"
