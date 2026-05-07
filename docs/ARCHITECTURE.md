# MailFlow — Architecture Overview

See `PLAN.md` section 5 for the detailed diagram. This document adds implementation notes.

## Key Components

### packages/core
Framework-agnostic Python library. Contains:
- `providers/` — EmailProvider abstract class + IMAP/M365/Gmail implementations
- `classification/` — deterministic cascade + LLM fallback (Phase 1)
- `drafts/` — draft generation + collision check (Phase 3)
- `templates/` — template matching and variable substitution (Phase 3)

### apps/api
FastAPI application. Thin HTTP layer over `packages/core`. Contains:
- `routers/` — one module per domain (accounts, rules, templates, drafts, cycles)
- `models/` — SQLAlchemy ORM models
- `schemas/` — Pydantic request/response schemas
- `auth/` — Better Auth JWT verification middleware

### apps/worker
ARQ async job runner. Main job: `process_account_cycle(account_id)`.
- Loads account config from DB
- Creates provider via factory
- Runs classification loop
- Saves drafts
- Persists cycle state + audit log

### apps/web
Next.js 15 App Router frontend.
- `app/[locale]/` — i18n routing with next-intl
- `app/[locale]/onboarding/` — 5-step wizard
- `app/[locale]/app/` — authenticated dashboard

## Classification Cascade

Priority order (higher wins, short-circuits on match):

1. Internal domain (igex.es, exclusivas-energeticas.com) → `Interno_IGEX` (confidence 1.0)
2. Known client domain → client folder (confidence 1.0)
3. Thread inheritance — reply to a classified email → same folder (confidence 0.95)
4. Keyword match → configured folder (confidence 0.80)
5. LLM classification → best-guess folder (confidence varies)
6. Fallback → `Sin_Clasificar`

Generic domains (gmail.com, hotmail.com, outlook.com, yahoo.com, icloud.com) do NOT match rule 2.

## IMAP Safety Rules (non-negotiable)

- Always use UIDs (`use_uid=True`)
- Detect folder separator dynamically via LIST
- Detect Drafts folder via `\Drafts` attribute, not by name
- Move sequence: COPY → verify OK → STORE +FLAGS \Deleted → EXPUNGE
  - If COPY fails, do NOT call EXPUNGE
- Check for existing user draft in thread before saving (ADR-004)
- Track UIDVALIDITY per folder; invalidate cache on change
