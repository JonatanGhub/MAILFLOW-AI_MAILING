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
    defaults = {
        "uid": 1,
        "subject_normalized": "Project proposal",
        "body_text": "Please review the attached proposal.",
        "body_html": "",
        "signature": "",
        "from_email": "contact@acmecorp.com",
        "from_domain": "acmecorp.com",
        "to_emails": ["me@company.com"],
        "in_reply_to": None,
        "thread_id": None,
        "date": None,
    }
    defaults.update(kwargs)
    return ParsedEmail(**defaults)


def base_config(**kwargs) -> AccountConfig:
    defaults = {
        "account_id": "acc-1",
        "internal_domains": ["company.com"],
        "client_domain_rules": [
            DomainRule(domain="acmecorp.com", label="acme", rule_id="rule-1"),
        ],
        "keyword_rules": [
            KeywordRule(keywords=("urgent", "asap"), label="priority", rule_id="kw-1"),
        ],
    }
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

    @pytest.mark.parametrize(
        "domain",
        [
            "gmail.com",
            "hotmail.com",
            "outlook.com",
            "yahoo.com",
            "yahoo.es",
            "icloud.com",
            "me.com",
            "protonmail.com",
            "proton.me",
            "live.com",
        ],
    )
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
        result = engine.classify(
            make_email(from_domain="unknown.net", subject_normalized="URGENT request")
        )
        assert result.label == "priority"
        assert result.confidence == 0.80
        assert result.method == "keyword"

    def test_or_match_second_keyword(self):
        engine = RuleEngine(base_config())
        result = engine.classify(
            make_email(from_domain="unknown.net", body_text="we need this asap")
        )
        assert result.label == "priority"

    def test_and_match_requires_all_keywords(self):
        config = base_config(
            keyword_rules=[
                KeywordRule(
                    keywords=("invoice", "overdue"), label="finance", rule_id="kw-2", match_all=True
                )
            ]
        )
        engine = RuleEngine(config)
        result = engine.classify(
            make_email(from_domain="unknown.net", body_text="The invoice is overdue.")
        )
        assert result.label == "finance"

    def test_and_match_partial_does_not_match(self):
        config = base_config(
            keyword_rules=[
                KeywordRule(
                    keywords=("invoice", "overdue"), label="finance", rule_id="kw-2", match_all=True
                )
            ]
        )
        engine = RuleEngine(config)
        result = engine.classify(
            make_email(from_domain="unknown.net", body_text="The invoice is pending.")
        )
        assert result.method != "keyword"

    def test_keyword_case_insensitive(self):
        engine = RuleEngine(base_config())
        result = engine.classify(
            make_email(from_domain="unknown.net", subject_normalized="URGENT matter")
        )
        assert result.method == "keyword"


class TestStep5LLMFallback:
    def test_uses_llm_when_no_rule_matches(self):
        mock_llm = MagicMock()
        mock_llm.classify.return_value = ClassificationResult(
            label="acme", confidence=0.75, method="llm"
        )
        engine = RuleEngine(
            base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm
        )
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "llm"
        assert result.label == "acme"

    def test_low_confidence_llm_falls_to_fallback(self):
        mock_llm = MagicMock()
        mock_llm.classify.return_value = ClassificationResult(
            label="maybe", confidence=0.40, method="llm"
        )
        engine = RuleEngine(
            base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm
        )
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "fallback"

    def test_llm_exception_falls_to_fallback(self):
        mock_llm = MagicMock()
        mock_llm.classify.side_effect = Exception("LLM unavailable")
        engine = RuleEngine(
            base_config(client_domain_rules=[], keyword_rules=[]), llm_client=mock_llm
        )
        result = engine.classify(make_email(from_domain="unknown.net"))
        assert result.method == "fallback"


class TestStep6Fallback:
    def test_fallback_when_no_rules_and_no_llm(self):
        engine = RuleEngine(AccountConfig(account_id="empty"))
        result = engine.classify(make_email(from_domain="totally.unknown"))
        assert result.label == "unclassified"
        assert result.confidence == 0.0
        assert result.method == "fallback"
