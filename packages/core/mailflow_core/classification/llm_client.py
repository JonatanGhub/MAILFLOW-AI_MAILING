"""LiteLLM wrapper for email classification and draft generation."""

from __future__ import annotations

import json
from dataclasses import dataclass

import litellm

from mailflow_core.exceptions import ClassificationError, LLMError
from mailflow_core.types import ClassificationResult, DraftRequest, ParsedEmail

_CLASSIFY_SYSTEM = (
    "You are an email classification assistant. "
    "Given an email, classify it into exactly one of the provided labels. "
    'Respond ONLY with a JSON object: {"label": "<label>", "confidence": <0.0-1.0>}. '
    "The label must be one of the provided options. No other text."
)

_DRAFT_SYSTEM = (
    "You are a professional email drafting assistant. "
    "Write a reply in the same language as the original email. "
    "Return only the body text — no subject line, no headers, no signature placeholder."
)


@dataclass
class LLMConfig:
    model_id: str
    api_base: str | None = None
    api_key: str | None = None
    timeout: float = 30.0
    max_retries: int = 2


class LLMClient:
    """Wrapper around litellm.completion for classify and generate_draft."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def _call(self, messages: list[dict]) -> str:
        kwargs: dict = {
            "model": self._config.model_id,
            "messages": messages,
            "timeout": self._config.timeout,
            "num_retries": self._config.max_retries,
        }
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    def classify(self, email: ParsedEmail, available_labels: list[str]) -> ClassificationResult:
        user_msg = (
            f"Labels: {', '.join(available_labels)}\n\n"
            f"Subject: {email.subject_normalized}\n"
            f"From: {email.from_email}\n\n"
            f"{email.body_text[:500]}"
        )
        raw = self._call(
            [
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": user_msg},
            ]
        )
        try:
            data = json.loads(raw)
            label = data["label"]
            confidence = float(data["confidence"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ClassificationError(f"Invalid LLM response: {raw!r}") from exc
        if label not in available_labels:
            raise ClassificationError(
                f"Label {label!r} not in available labels: {available_labels}"
            )
        return ClassificationResult(label=label, confidence=confidence, method="llm")

    def generate_draft(self, original_email: ParsedEmail, request: DraftRequest) -> str:
        user_msg = (
            f"Original email:\nSubject: {original_email.subject_normalized}\n"
            f"From: {original_email.from_email}\n\n"
            f"{original_email.body_text[:500]}\n\n"
            f"Classification: {request.classification.label}\n"
            f"Reply subject: {request.subject}"
        )
        return self._call(
            [
                {"role": "system", "content": _DRAFT_SYSTEM},
                {"role": "user", "content": user_msg},
            ]
        )
