"""Deterministic classification cascade for incoming emails."""
from __future__ import annotations

from dataclasses import dataclass, field

from mailflow_core.types import ClassificationResult, ParsedEmail

GENERIC_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.es",
    "icloud.com", "me.com", "protonmail.com", "proton.me", "live.com",
})


@dataclass(frozen=True)
class DomainRule:
    domain: str
    label: str
    rule_id: str


@dataclass(frozen=True)
class KeywordRule:
    keywords: tuple[str, ...]
    label: str
    rule_id: str
    match_all: bool = False


@dataclass
class AccountConfig:
    account_id: str
    internal_domains: list[str] = field(default_factory=list)
    client_domain_rules: list[DomainRule] = field(default_factory=list)
    keyword_rules: list[KeywordRule] = field(default_factory=list)


class RuleEngine:
    """Six-step classification cascade: domain → thread → keyword → LLM → fallback."""

    def __init__(self, config: AccountConfig, llm_client: object | None = None) -> None:
        self._config = config
        self._llm = llm_client

    def classify(
        self,
        email: ParsedEmail,
        thread_history: list[ClassificationResult] | None = None,
        available_labels: list[str] | None = None,
    ) -> ClassificationResult:
        labels = available_labels or [r.label for r in self._config.client_domain_rules] + ["unclassified"]

        # Step 1: internal domain
        if email.from_domain in self._config.internal_domains:
            return ClassificationResult(label="internal", confidence=1.0, method="domain_internal")

        # Step 2: known client domain (skip generic providers)
        if email.from_domain not in GENERIC_DOMAINS:
            for rule in self._config.client_domain_rules:
                if rule.domain == email.from_domain:
                    return ClassificationResult(
                        label=rule.label, confidence=0.95, method="domain_client", rule_id=rule.rule_id
                    )

        # Step 3: thread inheritance (most recent entry)
        if thread_history:
            last = thread_history[-1]
            if last.confidence >= 0.80:
                return ClassificationResult(label=last.label, confidence=0.90, method="thread")

        # Step 4: keyword match
        search_text = f"{email.subject_normalized} {email.body_text}".lower()
        for rule in self._config.keyword_rules:
            kws = [k.lower() for k in rule.keywords]
            matched = all(k in search_text for k in kws) if rule.match_all else any(k in search_text for k in kws)
            if matched:
                return ClassificationResult(
                    label=rule.label, confidence=0.80, method="keyword", rule_id=rule.rule_id
                )

        # Step 5: LLM fallback
        if self._llm is not None:
            try:
                result = self._llm.classify(email, available_labels=labels)
                if result.confidence >= 0.60:
                    return result
            except Exception:
                pass

        # Step 6: unclassified
        return ClassificationResult(label="unclassified", confidence=0.0, method="fallback")
