# ADR-001: SQLite for self-hosted mode, PostgreSQL for SaaS

**Date:** 2026-05-06
**Status:** Accepted

## Context

MailFlow supports two deployment modes:
- **SaaS** (`app.mailflow.app`): multi-tenant, needs row-level security, vector search (v2), concurrent writes
- **Self-hosted** (`docker compose up`): single user/org, minimal ops overhead, no cloud dependency

## Decision

- SaaS uses **PostgreSQL 17 + pgvector** with Row-Level Security on `org_id`
- Self-hosted uses **SQLite** (via `aiosqlite`) with a single "default-org"
- SQLAlchemy 2.0 async with the same ORM models for both; driver selected by `DATABASE_URL`
- Migration scripts provided for SQLite → Postgres for users who outgrow self-hosted

## Consequences

+ Zero external dependencies for self-hosted users (no Postgres required)
+ Same codebase, one schema
- SQLite has no native RLS; security is enforced in application layer for self-hosted
- pgvector semantic search (v2 feature) is SaaS-only unless user runs Postgres locally
