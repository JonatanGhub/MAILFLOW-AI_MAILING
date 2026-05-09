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
