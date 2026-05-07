# Contributing to MailFlow

Thank you for your interest in contributing! MailFlow is open source under AGPL-3.0.

## Development Setup

### Prerequisites
- Python 3.13+
- Node.js 20+
- pnpm 9+
- uv (Python package manager)
- Docker + Docker Compose (for local services)

### Quick Start

```bash
git clone https://github.com/JonatanGhub/mailflow.git
cd mailflow

# Start local services (Postgres + Redis)
docker compose -f infrastructure/docker-compose.dev.yml up -d postgres redis

# Backend
uv sync --all-packages
uvicorn apps.api.app.main:app --reload

# Frontend (separate terminal)
pnpm install
pnpm dev
```

### Running Tests

```bash
# Python tests
uv run pytest packages/core/tests/ --cov=mailflow_core --cov-fail-under=80

# Lint
uv run ruff check .
uv run ruff format --check .

# TypeScript
pnpm typecheck
pnpm biome check .
```

## Code Standards

- Python: follow `ruff` rules (see `pyproject.toml`)
- TypeScript: follow Biome rules
- Test coverage: 80% minimum for `packages/core`
- All functions < 50 lines, all files < 400 lines

## Pull Request Process

1. Fork the repo and create a branch: `feat/your-feature` or `fix/your-bug`
2. Write tests first (TDD)
3. Ensure CI passes (lint + tests)
4. Open a PR against `main` with a clear description

## Commit Message Format

```
feat: add Gmail OAuth2 provider
fix: handle UIDVALIDITY change in IMAP
docs: update self-hosting guide
test: add classification cascade tests
```

## Architecture Decisions

Read `docs/PLAN.md` and `docs/ARCHITECTURE.md` before making significant changes.
New architectural decisions go in `docs/adr/`.

## Code of Conduct

Be respectful. Focus on technical merit. English preferred in code/comments; Spanish is welcome in discussions.
