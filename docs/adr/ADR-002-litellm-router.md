# ADR-002: LiteLLM as the LLM router

**Date:** 2026-05-06
**Status:** Accepted

## Context

A key differentiator of MailFlow is multi-LLM support. Users must be able to choose
any model (Ollama local, OpenAI, Anthropic, Gemini, vLLM, LM Studio, etc.) per workspace.

## Decision

Use **LiteLLM** as the unified LLM router. It provides:
- 100+ provider integrations under a single OpenAI-compatible API
- Structured output (JSON schema) support
- Streaming support
- Budget and quota tracking per key
- AGPL-compatible license

Each workspace stores `(provider_type, base_url, api_key_ref, model)` in the DB.
The API builds a LiteLLM `completion()` call with those params at runtime.

## Consequences

+ Single integration point regardless of backend model
+ Easy to add new providers without code changes
+ Users can use fully local models with Ollama (no data leaves LAN)
- LiteLLM is a large dependency (~50 MB)
- Provider API changes can break LiteLLM compatibility temporarily
